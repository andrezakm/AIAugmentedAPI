#!/usr/bin/env python3
"""
Airtable Roadmap Store — reference client.

A clean, dependency-light realization of the access contract in
../AIRTABLE_ACCESS_SPEC.md and ../AIRTABLE_ROADMAP_SPEC.md. Drop it into another
project as-is, or read it as the canonical example of "how the access is done here".

It deliberately fixes two gaps in the original engine:
  • get_all_features() pages through *all* records (the original stopped at 100).
  • create_many() chunks batches to Airtable's hard limit of 10 records per call.

Requirement tags (Rn) refer to ../AIRTABLE_ROADMAP_SPEC.md §6.

    from airtable_client import AirtableRoadmap
    rm = AirtableRoadmap()                 # reads AIRTABLE_* from env / .env  (R13, R14)
    rm.health_check()                      # liveness + credentials
    for rec in rm.get_new_features():      # the auditor's queue              (R5)
        rm.update_feature(rec["id"], {     # write a verdict back             (R7,R9,R10)
            "Strategy Score": 8.7,         # → Roadmap_Lane auto-set to "Next" (R10)
            "Status": "Approved",
            "Claude Feedback": "Strong M2 reuse…",
            "Triad Balance": ["Brain", "Organs"],
            "Horizon": "H1→H2",
        })
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import requests
from dotenv import load_dotenv


# --- business rule: lane follows score (spec §10.1 / R10) --------------------
def lane_for_score(score: float) -> str:
    """≥9.0 → Now, 8.0–8.9 → Next, <8.0 → Later."""
    if score >= 9.0:
        return "Now"
    if score >= 8.0:
        return "Next"
    return "Later"


class AirtableRoadmap:
    """Roadmap store client: list / get / create / update + retry + pagination."""

    DATA_ROOT = "https://api.airtable.com/v0"
    META_ROOT = "https://api.airtable.com/v0/meta"
    BATCH_LIMIT = 10  # Airtable hard cap on records per create/update call

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        env_path: Optional[str] = None,
    ) -> None:
        # Config is environment-driven, never hardcoded (R14).
        if env_path:
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv()

        self.pat = os.getenv("AIRTABLE_PAT")
        self.base_id = os.getenv("AIRTABLE_BASE_ID")
        self.table = os.getenv("AIRTABLE_TABLE_NAME")
        if not all([self.pat, self.base_id, self.table]):
            raise ValueError(
                "Missing config. Set these (in .env or the environment):\n"
                "  AIRTABLE_PAT, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME"
            )

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.data_url = f"{self.DATA_ROOT}/{self.base_id}/{self.table}"
        self.meta_url = f"{self.META_ROOT}/bases/{self.base_id}/tables"
        # PAT bearer auth (R13). Content-Type required on writes, harmless on reads.
        self.headers = {
            "Authorization": f"Bearer {self.pat}",
            "Content-Type": "application/json",
        }

    # --- transport: retry + exponential backoff + 429 handling (R12) ---------
    def _request(self, method: str, url: str, **kw: Any) -> Optional[requests.Response]:
        for attempt in range(self.max_retries):
            try:
                r = requests.request(method, url, headers=self.headers, **kw)
                if r.status_code in (200, 201):
                    return r
                if r.status_code == 429:  # rate limited — honor Retry-After
                    wait = int(r.headers.get("Retry-After", self.retry_delay * (2 ** attempt)))
                    time.sleep(wait)
                    continue
                if 400 <= r.status_code < 500:  # client error — do not retry
                    return r
                # 5xx falls through to backoff
            except (requests.Timeout, requests.ConnectionError):
                pass  # transient — fall through to backoff
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (2 ** attempt))
        return None  # retries exhausted

    # --- reads ---------------------------------------------------------------
    def get_new_features(self) -> Optional[list[dict]]:
        """The unprocessed queue: Status == 'New' or blank, name-sorted (R5)."""
        return self._list(
            {
                "filterByFormula": "OR({Status}='New', {Status}=BLANK())",
                "sort[0][field]": "Feature Name",
                "sort[0][direction]": "asc",
            }
        )

    def get_all_features(self, max_records: Optional[int] = None) -> Optional[list[dict]]:
        """The whole portfolio, fully paginated (R6)."""
        return self._list(
            {"sort[0][field]": "Feature Name", "sort[0][direction]": "asc"},
            max_records=max_records,
        )

    def _list(self, params: dict, max_records: Optional[int] = None) -> Optional[list[dict]]:
        """GET with pagination. Returns [] when empty, None only if the FIRST page fails."""
        out: list[dict] = []
        offset: Optional[str] = None
        params = dict(params)
        if max_records:
            params["maxRecords"] = max_records
        first = True
        while True:
            if offset:
                params["offset"] = offset
            r = self._request("GET", self.data_url, params=params, timeout=30)
            if not r or r.status_code != 200:
                return None if first else out  # hard fail on page 1, else best-effort
            first = False
            body = r.json()
            out.extend(body.get("records", []))
            offset = body.get("offset")
            if not offset or (max_records and len(out) >= max_records):
                break
        return out

    def get_feature_by_id(self, record_id: str) -> Optional[dict]:
        """Fetch a single record by its stable id (R7)."""
        r = self._request("GET", f"{self.data_url}/{record_id}", timeout=30)
        return r.json() if r and r.status_code == 200 else None

    # --- writes --------------------------------------------------------------
    def create_feature(self, fields: dict, typecast: bool = True) -> Optional[str]:
        """Create one feature; returns its new record id (R8, R11)."""
        r = self._request(
            "POST", self.data_url, json={"fields": fields, "typecast": typecast}, timeout=30
        )
        return r.json().get("id") if r and r.status_code in (200, 201) else None

    def create_many(self, fields_list: list[dict], typecast: bool = True) -> list[Optional[str]]:
        """Batch-create, chunked to BATCH_LIMIT. Returns ids aligned to input order;
        a None marks a record whose chunk failed (R8)."""
        ids: list[Optional[str]] = []
        for i in range(0, len(fields_list), self.BATCH_LIMIT):
            chunk = fields_list[i : i + self.BATCH_LIMIT]
            payload = {"records": [{"fields": f} for f in chunk], "typecast": typecast}
            r = self._request("POST", self.data_url, json=payload, timeout=30)
            if r and r.status_code in (200, 201):
                ids.extend(rec.get("id") for rec in r.json().get("records", []))
            else:
                ids.extend([None] * len(chunk))
        return ids

    def update_feature(self, record_id: str, fields: dict, typecast: bool = True) -> bool:
        """Partial update by id; preserves untouched fields (PATCH). Derives
        Roadmap_Lane from Strategy Score when not supplied (R7, R9, R10, R11)."""
        fields = dict(fields)
        if "Strategy Score" in fields:
            try:
                score = float(fields["Strategy Score"])
                fields["Strategy Score"] = score  # keep it numeric
                fields.setdefault("Roadmap_Lane", lane_for_score(score))  # R10
            except (TypeError, ValueError):
                pass  # leave a non-numeric score for the API/typecast to reject
        r = self._request(
            "PATCH",
            f"{self.data_url}/{record_id}",
            json={"fields": fields, "typecast": typecast},
            timeout=30,
        )
        return bool(r and r.status_code == 200)

    def delete_feature(self, record_id: str) -> bool:
        """Delete one record. Not used by the running workflow — provided for
        completeness and to let the smoke test clean up after itself."""
        r = self._request("DELETE", f"{self.data_url}/{record_id}", timeout=30)
        return bool(r and r.status_code == 200)

    # --- ops -----------------------------------------------------------------
    def health_check(self) -> bool:
        """Cheap liveness + credentials probe (list one row)."""
        r = self._request("GET", self.data_url, params={"maxRecords": 1}, timeout=10)
        return bool(r and r.status_code == 200)

    def get_schema(self) -> Optional[dict]:
        """Metadata API: tables, field types, select choices. Needs schema.bases:read."""
        r = self._request("GET", self.meta_url, timeout=30)
        return r.json() if r and r.status_code == 200 else None


# --- CLI smoke ("python airtable_client.py") --------------------------------
def main() -> None:
    rm = AirtableRoadmap()
    print("Health:", "OK" if rm.health_check() else "FAIL")
    new = rm.get_new_features()
    print("New/unprocessed features:", "error" if new is None else len(new))
    allf = rm.get_all_features()
    print("Total features (paginated):", "error" if allf is None else len(allf))


if __name__ == "__main__":
    main()
