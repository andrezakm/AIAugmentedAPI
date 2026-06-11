# Kursumgebung: AI-Augmented PM — eine API aus einer Spec bauen

## Wer wir sind

NeoEmployee baut custom AI-Agenten, die Mitarbeiterfähigkeiten in Unternehmen ersetzen. Im PM-Workflow steuern diese Agenten eine **Roadmap** in Airtable: ein menschlicher PM trägt Feature-Ideen in eine Tabelle ein, ein KI-Auditor liest sie über die API, bewertet sie und schreibt ein Urteil zurück. Die Roadmap ist der gemeinsame Zustand, an dem Mensch und KI arbeiten. Dieses Modul baut genau diesen API-Zugriff — aus einer Spec.

## Pfadkonventionen

- **Spec** (die Anforderungen): `AIRTABLE_ROADMAP_SPEC.md` (das **Warum**); technisches Beiblatt `AIRTABLE_ACCESS_SPEC.md` (das **Wie**).
- **Eval** (die Abnahmekriterien, getrennt von der Spec — wie letzte Woche): `eval.md`.
- `README.md` ist die Handover-Doku des fertigen Beispiels.
- `reference/` ist **was wir gebaut haben** — der fertige Client + Tests (offline `test_airtable_client.py` + live `smoke_test.py`). Für den Lern-Track und den Endvergleich.
- Der **Bau-Track** baut in `build/` — ein frischer, anfangs leerer Ordner.
- `.env` (dein Secret) liegt im Modul-Root und **niemals** im Repo. `.env.example` ist die Vorlage.
- Skills liegen in `.claude/skills/`.

## Umgebung

- Python-Pakete **niemals global installieren**, niemals Python selbst installieren (kein brew, kein System-pip).
- venv nutzen: `python3 -m venv .venv` (falls nicht vorhanden), dann `source .venv/bin/activate && pip install -r reference/requirements.txt` (requests, python-dotenv; für die Tests zusätzlich `pytest`).
- Wenn das venv kaputt wirkt (ImportError trotz Installation): `.venv` löschen und neu anlegen — nicht reparieren.

## Sicherheit (gilt immer)

- Der `AIRTABLE_PAT` ist ein **Geheimnis**. Er gehört **ausschließlich** in `.env`.
- Den PAT **nie** in eine andere Datei schreiben, **nie** ausgeben (kein `cat .env`, kein `echo $AIRTABLE_PAT`), **nie** loggen, **nie** committen.
- `.env` steht in `.gitignore` und darf **nie** committet werden (vorher `git status`). Die Teilnehmer selbst committen nichts.
- Base-ID und Table-Name sind **keine** Geheimnisse — sie dürfen im Repo stehen.
- In Code: den PAT nur aus der Umgebung lesen (`os.getenv`), niemals hardcoden.

## Während des Kurses

- Claude **baut für die Teilnehmer** (in `build/`), test-first, aus **Spec und Eval** — nicht durch Kopieren aus `reference/`. `reference/` ist Nachschlagewerk und Vergleich.
- Die **mechanischen Schritte** (venv, `pip`, Tests ausführen) führt Claude aus. Teilnehmer kopieren höchstens ein Kommando oder geben einen kurzen Auftrag. Das **Einzige**, was nur sie selbst tun: den PAT auf airtable.com erstellen und in `.env` eintragen.
- Erfolg ist **nicht** in einem Schuss garantiert. Iteration (roter Test → nachbessern → grün) ist der Normalfall, kein Scheitern.
- **Teilnehmer committen nichts.** Nur das überproduct-Team veröffentlicht das Kurs-Paket (ohne `.env`, mit leerem `build/`), damit Teilnehmer es **clean** bekommen.

## Kurs starten

Sobald der Nutzer "starte den Kurs", "los geht's", "weiter" oder ähnliches sagt — führe `/kurs` aus. Starte ohne Vorrede.
