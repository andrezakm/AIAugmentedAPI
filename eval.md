# Eval: Airtable Roadmap — API-Zugriff

**Datum:** 2026-06-11
**Basis:** AIRTABLE_ROADMAP_SPEC.md (§11) + AIRTABLE_ACCESS_SPEC.md (§11)

---

## Anleitung

PASS = Bedingung erfüllt. FAIL = nicht erfüllt. UNKLAR = nicht aus Code oder Output entscheidbar.

**Ebene** sagt, was du zum Prüfen brauchst:
- **offline** — gemockte Tests, kein Airtable, kein PAT nötig.
- **live** — gegen die echte Base, braucht `.env` mit PAT.

Das ist die menschenlesbare Abnahme. Ihre **ausführbare** Form sind die Tests:
`reference/test_airtable_client.py` (offline) und `reference/smoke_test.py` (live).

## Kriterien

| ID | Kriterium | Ebene | Wie testen | Pass-Bedingung | Ergebnis |
|----|-----------|-------|------------|----------------|----------|
| E1 | Lane folgt aus Score | offline | Update mit Score, ohne Lane | 9.2 → Now, 8.7 → Next, 7.5 → Later | — |
| E2 | Voller Read paginiert | offline | Liste mit mehreren `offset`-Seiten mocken | alle Seiten zusammengeführt, nicht nur die ersten 100 | — |
| E3 | Retry-Vertrag | offline | 429 / 5xx / Timeout mocken, dann 200 | 429 (Retry-After) / 5xx / Timeout werden wiederholt; andere 4xx **nicht** | — |
| E4 | Batch ≤ 10 | offline | 23 Records anlegen | Chunks 10 / 10 / 3, nie > 10 pro Call | — |
| E5 | typecast immer | offline | Create + Update prüfen | jeder Write sendet `typecast: true` | — |
| E6 | PATCH, nicht PUT | offline | Update prüfen | Methode ist PATCH; nur genannte Felder ändern sich | — |
| E7 | Defensiv lesen | offline | Antwort ohne `Status` mocken; leeres Ergebnis | fehlendes Feld → `""`, leeres Ergebnis → `[]` (kein Crash) | — |
| E8 | Health | live | `GET ?maxRecords=1` | Status 200 | — |
| E9 | Schema | live | Meta-API lesen | Tabelle `Roadmap` mit allen 8 Feldern | — |
| E10 | Queue-Filter | live | `get_new_features` | nur `Status` New/leer, nach `Feature Name` sortiert | — |
| E11 | Ganze Roadmap | live | `get_all_features` | alle Records (auch > 100), nur lesend | — |
| E12 | Schreibzyklus | live | create → update(8.7) → get → delete | Lane wird `Next`, fremde Felder bleiben erhalten, Record danach gelöscht, kein Duplikat | — |
| S0 | Secret sicher | immer | Code / Logs / `git status` ansehen | PAT nur in `.env`; nie geloggt, nie ausgegeben, nie committet | — |
