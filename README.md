# AI Augmented API — Zugriff auf ein System aus einer Spec bauen

Ein Modul aus dem Kurs **AI Augmented PM** (überproduct). Es beantwortet die Frage, die jeder zuerst hat:

> **„Wie bekomme ich Zugriff auf ein System, für das es keinen fertigen Connector (MCP) gibt?"**

Beispiel: **Airtable**. Es gibt keinen Ein-Klick-Connector — aber Airtable hat eine API. Wir bauen den Zugang durch diese Tür: **test-first, aus einer Spec**. Am Ende kann ein Skript für dich aus deiner Airtable-Tabelle lesen und hineinschreiben — und du weißt, wo dein API-Key hingehört (und wo nicht).

Du musst nicht programmieren. Das meiste macht Claude; du dirigierst, prüfst ab und sicherst den Schlüssel.

## So startest du

Öffne diesen Ordner in **Claude Code** und sag:

> **„starte den Kurs"**

Der Kurs (`/kurs`) führt dich in **8 Schritten** durch alles — auch wie du dir einen Airtable-Token besorgst (Schritt 3) und sicher hinterlegst.

Du musst **nichts** installieren oder tippen: Claude richtet die Umgebung ein, schreibt die Tests und führt sie aus. Das **Einzige**, was nur du tun kannst, ist den Token zu erstellen und in `.env` einzutragen.

## Voraussetzungen

- **Claude Code**
- **Python 3** (`python3 --version`)
- Für den Live-Teil: ein **Airtable-Account** + ein **Personal Access Token (PAT)**. Ohne Token kommst du trotzdem durch die ersten Schritte — die Offline-Tests brauchen kein Airtable.

## Lieber selbst per Terminal? (optional)

Im Kurs macht Claude das alles für dich — die folgenden Befehle brauchst du **nicht**. Nur falls du die fertige Beispiel-Lösung in `reference/` direkt selbst ausführen willst:

<details>
<summary>Befehle anzeigen</summary>

```bash
cp .env.example .env     # PAT eintragen (Kurs Schritt 3 erklärt, wie du ihn bekommst)
python3 -m venv .venv && source .venv/bin/activate
pip install -r reference/requirements.txt pytest

pytest reference/ -q                          # Offline-Tests (kein Airtable, kein Token nötig)
python reference/smoke_test.py                # Live-Check gegen deine Base (nur lesen)
python reference/smoke_test.py --write-cycle  # inkl. anlegen → prüfen → löschen
```
</details>

## Was drin ist

| Datei / Ordner | Was es ist |
|---|---|
| `AIRTABLE_ROADMAP_SPEC.md` | **Die Spec** — was der Zugriff können muss (das Warum). |
| `AIRTABLE_ACCESS_SPEC.md` | Technisches Beiblatt — Endpoints, JSON, Retry-Vertrag (das Wie). |
| `eval.md` | **Die Eval** — die Abnahmekriterien (wann es gut ist). |
| `reference/` | **Was wir gebaut haben** — fertiger Client + Tests, zum Studieren und Vergleichen. |
| `build/` | Dein **Bau-Ordner** — hier entsteht im Kurs dein eigener Client (am Anfang leer). |
| `.env.example` | Vorlage für deine Zugangsdaten. Kopierst du nach `.env`. |

## Das System, um das es geht

Beispiel: eine **Roadmap-Tabelle** in Airtable. Ein Mensch trägt Feature-Ideen ein; eine KI liest sie über die API, bewertet sie und schreibt ihr Urteil zurück. Einfach gesagt: **die Übergabe zwischen Mensch und KI passiert in der Tabelle.**

Datenmodell (Tabelle `Roadmap`):

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

## Sicherheit (das Wichtigste)

- Der **PAT** ist das **einzige Geheimnis**. Er gehört **nur** in `.env` — die steht in `.gitignore` und wird **nie** committet.
- `.env.example` enthält nur Platzhalter und darf geteilt werden.
- **Base-ID und Tabellenname sind keine Geheimnisse.**
- Token versehentlich öffentlich geworden? Auf airtable.com einen neuen erstellen, den alten zurückziehen.

## Gut zu wissen (die nicht offensichtlichen Stellen)

Diese Regeln leben im **Client**, nicht in Airtable — der Kurs baut sie test-first nach:

1. **Pagination ist Pflicht.** Airtable liefert max. 100 Zeilen pro Seite plus ein `offset`. Ohne die Schleife siehst du ab Zeile 101 nichts mehr.
2. **Batch-Writes max. 10 pro Call.** Mehr → `422`. Größere Mengen in Chunks aufteilen.
3. **Rate-Limit ~5 Requests/Sek.** Drüber → `429`. Der Client wiederholt mit Backoff und beachtet `Retry-After`.
4. **`typecast: true` bei jedem Write.** Sonst wird ein neuer Select-Wert mit `422` abgelehnt.
5. **Leere Felder fehlen in der Antwort.** „Status fehlt" und „Status = New" sind beide der unverarbeitete Zustand — immer defensiv lesen (`fields.get("Status", "")`).
6. **Lane folgt aus dem Score** — im Client gerechnet (≥9 → Now, 8.0–8.9 → Next, <8 → Later), nicht in Airtable.
7. **`PATCH`, nicht `PUT`.** PATCH lässt die übrigen Felder des Menschen stehen; PUT löscht sie.

## Abnahme

Die Kriterien stehen in [`eval.md`](eval.md). Ausführbar sind sie als Tests: `reference/test_airtable_client.py` (offline) und `reference/smoke_test.py` (live). Alles grün = fertig.
