#!/usr/bin/env python3
"""
Acceptance / smoke test for the Roadmap Store client.

Exercises the acceptance criteria from ../AIRTABLE_ROADMAP_SPEC.md §11.

Read-only by default (safe to run against the live base):
    python smoke_test.py

Add a full write→update→delete round-trip (creates a clearly-marked temp record,
verifies lane derivation, then deletes it):
    python smoke_test.py --write-cycle
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # the handover/ dir, where .env should live
sys.path.insert(0, str(HERE))

from airtable_client import AirtableRoadmap, lane_for_score  # noqa: E402

EXPECTED_FIELDS = {
    "Feature Name",
    "Description",
    "Status",
    "Strategy Score",
    "Roadmap_Lane",
    "Triad Balance",
    "Horizon",
    "Claude Feedback",
}

passed = 0
failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    mark = "✅" if ok else "❌"
    print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
    if ok:
        passed += 1
    else:
        failed += 1


def main() -> int:
    write_cycle = "--write-cycle" in sys.argv

    # --- pure-function checks: lane-from-score (R10), no network -------------
    print("\nBusiness rule — lane_for_score (R10):")
    check("9.2 → Now", lane_for_score(9.2) == "Now")
    check("8.7 → Next", lane_for_score(8.7) == "Next")
    check("7.5 → Later", lane_for_score(7.5) == "Later")

    env = ROOT / ".env"
    rm = AirtableRoadmap(env_path=str(env) if env.exists() else None)

    # --- connectivity & schema (R13, R3) ------------------------------------
    print("\nConnectivity & schema:")
    check("health_check", rm.health_check())

    schema = rm.get_schema()
    if schema is None:
        check("get_schema (needs schema.bases:read)", False, "no schema returned")
    else:
        target = next(
            (t for t in schema.get("tables", []) if t["name"] == rm.table or t["id"] == rm.table),
            None,
        )
        check("target table present", target is not None, rm.table)
        if target:
            names = {f["name"] for f in target.get("fields", [])}
            missing = EXPECTED_FIELDS - names
            check("all 8 expected fields present", not missing, f"missing={missing or 'none'}")

    # --- reads (R5, R6) -----------------------------------------------------
    print("\nReads:")
    new = rm.get_new_features()
    check("get_new_features returns a list", isinstance(new, list),
          f"{len(new) if isinstance(new, list) else new} unprocessed")
    if isinstance(new, list):
        bad = [r for r in new if (r.get("fields", {}).get("Status") or "New") not in ("New",)]
        check("queue contains only New/blank", not bad, f"{len(bad)} off-status rows")

    allf = rm.get_all_features()
    check("get_all_features returns a list (paginated)", isinstance(allf, list),
          f"{len(allf) if isinstance(allf, list) else allf} total")

    # --- optional write→update→delete round-trip (R7, R8, R10, R11) ---------
    if write_cycle:
        print("\nWrite cycle (creates a temp record, then deletes it):")
        rec_id = rm.create_feature(
            {
                "Feature Name": "ZZZ SMOKE TEST — safe to delete",
                "Description": "Temporary record created by smoke_test.py. Delete me.",
                "Status": "New",
            }
        )
        check("create_feature returns an id", bool(rec_id), str(rec_id))
        if rec_id:
            ok = rm.update_feature(rec_id, {"Strategy Score": 8.7, "Status": "Approved"})
            check("update_feature succeeds", ok)
            fetched = rm.get_feature_by_id(rec_id) or {}
            lane = fetched.get("fields", {}).get("Roadmap_Lane")
            check("lane auto-derived to 'Next' for score 8.7", lane == "Next", f"lane={lane}")
            check("delete_feature cleans up", rm.delete_feature(rec_id))
    else:
        print("\nWrite cycle: skipped (pass --write-cycle to run it).")

    print(f"\n{'='*48}\nPassed {passed} / {passed + failed} checks")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
