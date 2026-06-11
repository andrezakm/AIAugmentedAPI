#!/usr/bin/env python3
"""
Live-/Smoke-Test für den Roadmap-Client — prüft die Eval-Kriterien aus ../eval.md.

Read-only per Default (sicher gegen die Live-Base):
    python smoke_test.py

Mit Schreibzyklus (legt einen klar markierten Temp-Record an, prüft die Lane,
löscht ihn wieder):
    python smoke_test.py --write-cycle

Jeder Check ist mit seiner Eval-ID markiert. Am Ende kommt eine **Scorecard** mit
PASS/FAIL je Kriterium — genau die Spalte "Ergebnis" aus ../eval.md.
(E2–E7 prüft `pytest reference/`; S0 ist ein Sicht-Check.)
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # Modul-Root, hier liegt .env
sys.path.insert(0, str(HERE))

from airtable_client import AirtableRoadmap, lane_for_score  # noqa: E402

EXPECTED_FIELDS = {
    "Feature Name", "Description", "Status", "Strategy Score",
    "Roadmap_Lane", "Triad Balance", "Horizon", "Claude Feedback",
}

# Eval-Kriterium → PASS, solange JEDER zugehörige Check grün ist.
results: dict[str, bool] = {}


def check(eid: str, name: str, ok: bool, detail: str = "") -> None:
    mark = "✅" if ok else "❌"
    print(f"  {mark} {eid} · {name}" + (f" — {detail}" if detail else ""))
    results[eid] = results.get(eid, True) and ok


def main() -> int:
    write_cycle = "--write-cycle" in sys.argv

    print("\nLane (offline) — E1:")
    check("E1", "9.2 → Now", lane_for_score(9.2) == "Now")
    check("E1", "8.7 → Next", lane_for_score(8.7) == "Next")
    check("E1", "7.5 → Later", lane_for_score(7.5) == "Later")

    env = ROOT / ".env"
    rm = AirtableRoadmap(env_path=str(env) if env.exists() else None)

    print("\nVerbindung & Schema:")
    check("E8", "health_check", rm.health_check())
    schema = rm.get_schema()
    if schema is None:
        check("E9", "Schema (braucht schema.bases:read)", False, "kein Schema")
    else:
        target = next((t for t in schema.get("tables", [])
                       if t["name"] == rm.table or t["id"] == rm.table), None)
        check("E9", "Tabelle vorhanden", target is not None, rm.table)
        if target:
            names = {f["name"] for f in target.get("fields", [])}
            missing = EXPECTED_FIELDS - names
            check("E9", "alle 8 Felder vorhanden", not missing, f"fehlt={missing or 'nichts'}")

    print("\nLesen:")
    new = rm.get_new_features()
    check("E10", "get_new_features → Liste", isinstance(new, list),
          f"{len(new) if isinstance(new, list) else new} offen")
    if isinstance(new, list):
        bad = [r for r in new if (r.get("fields", {}).get("Status") or "New") not in ("New",)]
        check("E10", "Queue nur New/leer", not bad, f"{len(bad)} off-status")
    allf = rm.get_all_features()
    check("E11", "get_all_features → Liste (paginiert)", isinstance(allf, list),
          f"{len(allf) if isinstance(allf, list) else allf} gesamt")

    if write_cycle:
        print("\nSchreibzyklus (anlegen → prüfen → löschen):")
        rec_id = rm.create_feature({
            "Feature Name": "ZZZ SMOKE TEST — safe to delete",
            "Description": "Temporärer Record vom smoke_test. Bitte löschen.",
            "Status": "New",
        })
        check("E12", "create → id", bool(rec_id), str(rec_id))
        if rec_id:
            check("E12", "update", rm.update_feature(rec_id, {"Strategy Score": 8.7, "Status": "Approved"}))
            fetched = rm.get_feature_by_id(rec_id) or {}
            lane = fetched.get("fields", {}).get("Roadmap_Lane")
            check("E12", "Lane 8.7 → Next (live)", lane == "Next", f"lane={lane}")
            check("E12", "delete (Aufräumen)", rm.delete_feature(rec_id))
    else:
        print("\nSchreibzyklus (E12): übersprungen — mit --write-cycle ausführen.")

    # --- Eval-Scorecard: spiegelt die Spalte "Ergebnis" aus ../eval.md --------
    print(f"\n{'=' * 48}\nEval-Scorecard (→ ../eval.md):")
    for eid in ("E1", "E8", "E9", "E10", "E11", "E12"):
        if eid in results:
            print(f"  {eid:<4} {'PASS' if results[eid] else 'FAIL'}")
        elif eid == "E12":
            print("  E12  übersprungen (kein --write-cycle)")
    print("  E2–E7  offline via `pytest reference/`")
    print("  S0     Sicht-Check: PAT nur in .env, nie geloggt/committet")

    failed = sum(1 for v in results.values() if not v)
    passed = len(results) - failed
    print(f"\n{passed}/{len(results)} geprüfte Kriterien grün")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
