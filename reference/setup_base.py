#!/usr/bin/env python3
"""
Richtet die Roadmap-Tabelle in DEINER (leeren) Airtable-Base ein — die 8 Felder
mit den richtigen Typen und Select-Optionen. Ein API-Call, kein Handanlegen.

Braucht in .env:  AIRTABLE_PAT (mit Scope schema.bases:write!), AIRTABLE_BASE_ID
Lauf:             python reference/setup_base.py

Idempotent: existiert die Tabelle schon, passiert nichts. Der PAT wird nie ausgegeben.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PAT = os.getenv("AIRTABLE_PAT")
BASE = os.getenv("AIRTABLE_BASE_ID")
TABLE = os.getenv("AIRTABLE_TABLE_NAME", "Roadmap")
if not all([PAT, BASE]):
    sys.exit("Fehlt: AIRTABLE_PAT und/oder AIRTABLE_BASE_ID in .env")

META = f"https://api.airtable.com/v0/meta/bases/{BASE}/tables"
HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

# Die 8 Felder aus der Spec. Erstes Feld = Primaerfeld (Text).
FIELDS = [
    {"name": "Feature Name", "type": "singleLineText"},
    {"name": "Description", "type": "multilineText"},
    {"name": "Status", "type": "singleSelect", "options": {"choices": [
        {"name": "New"}, {"name": "Needs More Information"}, {"name": "Needs Refinement"},
        {"name": "Approved"}, {"name": "Draft"}, {"name": "In Review"}, {"name": "UI Ready"},
    ]}},
    {"name": "Strategy Score", "type": "number", "options": {"precision": 1}},
    {"name": "Roadmap_Lane", "type": "singleSelect", "options": {"choices": [
        {"name": "Now"}, {"name": "Next"}, {"name": "Later"},
    ]}},
    {"name": "Triad Balance", "type": "multipleSelects", "options": {"choices": [
        {"name": "Brain"}, {"name": "Nervous System"}, {"name": "Organs"},
    ]}},
    {"name": "Horizon", "type": "singleSelect", "options": {"choices": [
        {"name": "H1"}, {"name": "H2"}, {"name": "H3"}, {"name": "H1->H2"}, {"name": "H2->H3"},
    ]}},
    {"name": "Claude Feedback", "type": "multilineText"},
]


def main() -> int:
    # Schon da? Dann nichts tun.
    r = requests.get(META, headers=HEADERS, timeout=30)
    if r.status_code == 401:
        sys.exit("FEHLER 401: Token ungueltig.")
    if r.status_code == 403:
        sys.exit("FEHLER 403: dem Token fehlt ein Scope (schema.bases:read/write?) "
                 "oder der Zugriff auf diese Base.")
    if r.status_code != 200:
        sys.exit(f"FEHLER beim Lesen der Tabellen: {r.status_code} {r.text[:200]}")

    tables = r.json().get("tables", [])
    found = next((t for t in tables if t["name"] == TABLE), None)
    if found:
        # Tabelle existiert — fehlende Felder ergaenzen (robust, falls jemand eine
        # vorhandene oder umbenannte Tabelle nutzt, statt Claude eine neue anlegen zu lassen).
        have = {f["name"] for f in found.get("fields", [])}
        missing = [f for f in FIELDS if f["name"] not in have]
        if not missing:
            print(f"OK: Tabelle '{TABLE}' hat schon alle {len(FIELDS)} Felder — nichts zu tun.")
            return 0
        url = f"{META}/{found['id']}/fields"
        for f in missing:
            rr = requests.post(url, headers=HEADERS, json=f, timeout=30)
            if rr.status_code not in (200, 201):
                sys.exit(f"FEHLER beim Feld '{f['name']}': {rr.status_code} {rr.text[:200]}")
        print(f"OK: Tabelle '{TABLE}' um {len(missing)} Feld(er) ergaenzt:")
        for f in missing:
            print(f"   + {f['name']}")
        return 0

    # Tabelle neu anlegen.
    r = requests.post(META, headers=HEADERS, json={"name": TABLE, "fields": FIELDS}, timeout=30)
    if r.status_code not in (200, 201):
        sys.exit(f"FEHLER beim Anlegen: {r.status_code} {r.text[:300]}")

    names = [f["name"] for f in r.json().get("fields", [])]
    print(f"OK: Tabelle '{TABLE}' angelegt mit {len(names)} Feldern:")
    for n in names:
        print(f"   - {n}")
    print("\nFertig — jetzt laeuft der Live-Test gegen deine eigene Base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
