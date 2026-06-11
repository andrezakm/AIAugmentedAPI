# AI Augmented API — Zugriff auf ein System aus einer Spec bauen

Ein Modul aus dem Kurs **AI Augmented PM** (überproduct). Es beantwortet die Frage, die jeder zuerst hat:

> **„Wie bekomme ich Zugriff auf ein System, für das es keinen fertigen Connector (MCP) gibt?"**

Beispiel: **Airtable**. Es gibt keinen Ein-Klick-Connector — aber Airtable hat eine API. Wir bauen den Zugang durch diese Tür: **test-first, aus einer Spec**. Am Ende kann ein Skript für dich aus deiner Airtable-Tabelle lesen und hineinschreiben — und du weißt, wo dein API-Key hingehört.

**Du musst nicht programmieren.** Das meiste macht Claude; du dirigierst, prüfst ab und sicherst den Schlüssel.

## So startest du

Öffne diesen Ordner in **Claude Code** und sag:

> **„starte den Kurs"**

Der Kurs (`/kurs`) führt dich in **8 Schritten** durch alles. Claude richtet die Umgebung ein, schreibt die Tests und führt sie aus — du musst **nichts** installieren oder tippen.

Das **Einzige**, was nur du tun kannst: dir einen Airtable-Token erstellen und eintragen. Wie das geht, zeigt dir der Kurs Klick für Klick (Schritt 3).

## Was du brauchst

- **Claude Code** (das hier).
- Einen **Airtable-Account** (kostenlos).

Mehr nicht. Python und alles Weitere richtet Claude im Kurs für dich ein.

## Was drin ist

| Datei / Ordner | Was es ist |
|---|---|
| `AIRTABLE_ROADMAP_SPEC.md` | **Die Spec** — was der Zugriff können muss (das Warum). |
| `AIRTABLE_ACCESS_SPEC.md` | Technisches Beiblatt — die genauen Details (das Wie). |
| `eval.md` | **Die Eval** — die Abnahmekriterien (wann es gut ist). |
| `reference/` | **Was wir gebaut haben** — fertiger Client + Tests, zum Studieren und Vergleichen. |
| `build/` | Dein **Bau-Ordner** — hier entsteht im Kurs dein eigener Client (am Anfang leer). |
| `.env.example` | Vorlage für deine Zugangsdaten. |

## Das System, um das es geht

Beispiel: eine **Roadmap-Tabelle** in Airtable. Ein Mensch trägt Feature-Ideen ein; eine KI liest sie über die API, bewertet sie und schreibt ihr Urteil zurück. Einfach gesagt: **die Übergabe zwischen Mensch und KI passiert in der Tabelle.**

<details>
<summary>Datenmodell der Tabelle (zum Nachschlagen)</summary>

| Feld | Typ | Werte |
|---|---|---|
| Feature Name | singleLineText | Primärfeld |
| Description | richText | Markdown |
| Status | singleSelect | New · Needs More Information · Needs Refinement · Approved · Draft · In Review · UI Ready |
| Strategy Score | number (1 Dezimal) | 1.0–10.0 |
| Roadmap_Lane | singleSelect | Now · Next · Later (wird aus dem Score abgeleitet) |
| Triad Balance | multipleSelects | Brain · Nervous System · Organs |
| Horizon | singleSelect | H1 · H2 · H3 · H1→H2 · H2→H3 |
| Claude Feedback | multilineText | Begründung / Rückfragen der KI an den Menschen |
</details>

## Sicherheit (das Wichtigste)

- Dein **Token (PAT)** ist das **einzige Geheimnis**. Er gehört **nur** in die Datei `.env` — die wird **nie** geteilt und nie öffentlich hochgeladen.
- `.env.example` enthält nur Platzhalter und darf geteilt werden.
- **Base-ID und Tabellenname sind keine Geheimnisse.**
- Token versehentlich öffentlich geworden? Auf airtable.com einen neuen erstellen, den alten zurückziehen — fertig.

## Für Technik-Interessierte (optional)

Alles hier ist **freiwillig** — im Kurs übernimmt das Claude.

<details>
<summary>Die fertige Lösung selbst im Terminal ausführen</summary>

```bash
cp .env.example .env     # PAT eintragen (Kurs Schritt 3 erklärt, wie du ihn bekommst)
python3 -m venv .venv && source .venv/bin/activate
pip install -r reference/requirements.txt pytest

pytest reference/ -q                          # Offline-Tests (kein Airtable, kein Token nötig)
python reference/smoke_test.py                # Live-Check gegen deine Base (nur lesen)
python reference/smoke_test.py --write-cycle  # inkl. anlegen → prüfen → löschen
```
</details>

<details>
<summary>Sieben Stolpersteine, die der Client test-first löst</summary>

Diese Regeln leben im **Client**, nicht in Airtable:

1. **Pagination ist Pflicht.** Airtable liefert max. 100 Zeilen pro Seite plus ein `offset`. Ohne die Schleife siehst du ab Zeile 101 nichts mehr.
2. **Batch-Writes max. 10 pro Call.** Mehr → `422`. Größere Mengen in Chunks aufteilen.
3. **Rate-Limit ~5 Requests/Sek.** Drüber → `429`. Der Client wiederholt mit Backoff.
4. **`typecast: true` bei jedem Write.** Sonst wird ein neuer Select-Wert mit `422` abgelehnt.
5. **Leere Felder fehlen in der Antwort.** „Status fehlt" und „Status = New" sind beide der unverarbeitete Zustand — immer defensiv lesen.
6. **Lane folgt aus dem Score** — im Client gerechnet (≥9 → Now, 8.0–8.9 → Next, <8 → Later).
7. **`PATCH`, nicht `PUT`.** PATCH lässt die übrigen Felder stehen; PUT löscht sie.
</details>

<details>
<summary>Abnahmekriterien</summary>

Die Kriterien stehen in [`eval.md`](eval.md). Ausführbar als Tests: `reference/test_airtable_client.py` (offline) und `reference/smoke_test.py` (live). Alles grün = fertig.
</details>
