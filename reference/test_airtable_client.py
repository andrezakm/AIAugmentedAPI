#!/usr/bin/env python3
"""
Offline unit tests for the Roadmap Store client — the *first* of the two test
layers (the second is the live smoke_test.py).

These tests use mocked HTTP responses, so they need **no Airtable account, no
network, and no PAT**. They prove the client-side invariants from
../AIRTABLE_ROADMAP_SPEC.md §10 and the retry contract from
../AIRTABLE_ACCESS_SPEC.md §7:

  • pagination loops over `offset` across multiple pages
  • lane-from-score derivation (and auto-lane on update)
  • retry on 429 / 5xx / Timeout, and NO retry on other 4xx
  • batch create chunks to ≤ 10 records per call
  • `typecast: true` is sent on every write
  • update uses PATCH (partial), not PUT
  • reads are defensive: empty queue → [], first-page failure → None

Run:  pytest reference/test_airtable_client.py -q
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Dummy config so the client constructs without a real .env / PAT. load_dotenv()
# does not override already-set env vars, so these win and no secret is needed.
os.environ.setdefault("AIRTABLE_PAT", "pat_dummy_for_tests")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTEST0000000000")
os.environ.setdefault("AIRTABLE_TABLE_NAME", "Roadmap")

from airtable_client import AirtableRoadmap, lane_for_score  # noqa: E402


def resp(status=200, body=None, headers=None):
    """Build a fake requests.Response."""
    r = MagicMock(spec=requests.Response)
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.headers = headers or {}
    return r


@pytest.fixture
def client():
    # retry_delay=0 → backoff sleeps are instant, tests stay fast.
    return AirtableRoadmap(max_retries=3, retry_delay=0)


# --- lane-from-score (§10.1) -------------------------------------------------
@pytest.mark.parametrize(
    "score,lane",
    [(9.2, "Now"), (9.0, "Now"), (8.9, "Next"), (8.0, "Next"), (7.9, "Later"), (7.5, "Later")],
)
def test_lane_for_score(score, lane):
    assert lane_for_score(score) == lane


# --- pagination over multiple pages (§9.2 / R6) ------------------------------
def test_get_all_features_paginates(client):
    pages = [
        resp(200, {"records": [{"id": "rec1"}, {"id": "rec2"}], "offset": "PAGE2"}),
        resp(200, {"records": [{"id": "rec3"}]}),  # no offset → last page
    ]
    with patch("airtable_client.requests.request", side_effect=pages) as m:
        out = client.get_all_features()
    assert [r["id"] for r in out] == ["rec1", "rec2", "rec3"]
    assert m.call_count == 2  # it actually looped to page 2


def test_empty_queue_is_list_not_none(client):
    with patch("airtable_client.requests.request", return_value=resp(200, {"records": []})):
        assert client.get_new_features() == []  # empty != error


def test_first_page_failure_returns_none(client):
    with patch("airtable_client.requests.request", return_value=resp(500, {})):
        assert client.get_all_features() is None


def test_record_without_status_does_not_crash(client):
    # "empty fields are omitted" — a record may simply lack Status; reads must cope.
    body = {"records": [{"id": "rec1", "fields": {"Feature Name": "X"}}]}
    with patch("airtable_client.requests.request", return_value=resp(200, body)):
        out = client.get_new_features()
    assert out[0]["fields"].get("Status", "") == ""


# --- auto-lane + PATCH + typecast on update (§10 / R7,R10,R11) ----------------
def test_update_derives_lane_and_uses_patch_with_typecast(client):
    with patch("airtable_client.requests.request", return_value=resp(200, {"id": "rec1"})) as m:
        ok = client.update_feature("rec1", {"Strategy Score": 8.7, "Status": "Approved"})
    assert ok
    method, url = m.call_args.args[0], m.call_args.args[1]
    payload = m.call_args.kwargs["json"]
    assert method == "PATCH"  # partial update, never PUT
    assert url.endswith("/rec1")
    assert payload["fields"]["Roadmap_Lane"] == "Next"  # 8.7 → Next, derived client-side
    assert payload["typecast"] is True


@pytest.mark.parametrize("score,lane", [(9.2, "Now"), (8.7, "Next"), (7.5, "Later")])
def test_update_auto_lane_matrix(client, score, lane):
    with patch("airtable_client.requests.request", return_value=resp(200, {"id": "r"})) as m:
        client.update_feature("r", {"Strategy Score": score})
    assert m.call_args.kwargs["json"]["fields"]["Roadmap_Lane"] == lane


def test_explicit_lane_is_not_overwritten(client):
    with patch("airtable_client.requests.request", return_value=resp(200, {"id": "r"})) as m:
        client.update_feature("r", {"Strategy Score": 9.5, "Roadmap_Lane": "Later"})
    assert m.call_args.kwargs["json"]["fields"]["Roadmap_Lane"] == "Later"  # caller wins


# --- create: typecast + batch chunking ≤ 10 (§6.3 / R8,R11) -------------------
def test_create_feature_sends_typecast_and_returns_id(client):
    with patch("airtable_client.requests.request", return_value=resp(200, {"id": "recNEW"})) as m:
        rid = client.create_feature({"Feature Name": "X"})
    assert rid == "recNEW"
    assert m.call_args.args[0] == "POST"
    assert m.call_args.kwargs["json"]["typecast"] is True


def test_create_many_chunks_at_ten(client):
    # 23 records → chunks of 10, 10, 3.
    def chunk_resp(*args, **kwargs):
        n = len(kwargs["json"]["records"])
        assert n <= 10  # never exceed Airtable's hard cap
        return resp(200, {"records": [{"id": f"rec{i}"} for i in range(n)]})

    with patch("airtable_client.requests.request", side_effect=chunk_resp) as m:
        ids = client.create_many([{"Feature Name": f"F{i}"} for i in range(23)])
    assert m.call_count == 3
    assert [len(c.kwargs["json"]["records"]) for c in m.call_args_list] == [10, 10, 3]
    assert len(ids) == 23 and all(ids)


# --- retry contract (§7 / R12) -----------------------------------------------
def test_retry_on_429_then_succeeds(client):
    seq = [resp(429, {}, {"Retry-After": "0"}), resp(200, {})]
    with patch("airtable_client.requests.request", side_effect=seq) as m:
        assert client.health_check() is True
    assert m.call_count == 2


def test_retry_on_5xx_then_succeeds(client):
    seq = [resp(500, {}), resp(200, {})]
    with patch("airtable_client.requests.request", side_effect=seq) as m:
        assert client.health_check() is True
    assert m.call_count == 2


def test_retry_on_timeout_then_succeeds(client):
    seq = [requests.Timeout("boom"), resp(200, {})]
    with patch("airtable_client.requests.request", side_effect=seq) as m:
        assert client.health_check() is True
    assert m.call_count == 2


def test_no_retry_on_404(client):
    with patch("airtable_client.requests.request", return_value=resp(404, {})) as m:
        assert client.get_feature_by_id("recX") is None
    assert m.call_count == 1  # client errors (≠429) are NOT retried


def test_retries_exhausted_returns_none(client):
    with patch("airtable_client.requests.request", return_value=resp(503, {})) as m:
        assert client.health_check() is False
    assert m.call_count == 3  # max_retries


# --- health (§6.5) -----------------------------------------------------------
def test_health_check_true_false(client):
    with patch("airtable_client.requests.request", return_value=resp(200, {})):
        assert client.health_check() is True
    with patch("airtable_client.requests.request", return_value=resp(401, {})):
        assert client.health_check() is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
