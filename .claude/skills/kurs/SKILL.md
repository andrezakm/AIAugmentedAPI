---
disable-model-invocation: true
---

# Kurs: Zugriff auf ein System bauen, für das es keinen Connector gibt

Willkommen. Die Frage, um die es hier geht:

> **„Wie bekomme ich Zugriff auf ein System, für das es keinen fertigen Connector (MCP) gibt?"**

Beispiel: **Airtable**. Es gibt keinen Ein-Klick-Connector — aber Airtable hat eine **API** (eine Tür, durch die Programme reindürfen). Wir bauen den Zugang durch diese Tür. Am Ende kann ein Skript für dich aus deiner Airtable-Tabelle lesen und hineinschreiben.

**Du musst nicht programmieren.** Das meiste macht **Claude**. So liest du diesen Kurs:

- 🟦 **Claude macht das** — du sagst „mach das" oder „weiter", Claude führt die Kommandos aus.
- ⌨️ **Kopier das** — manchmal kopierst du ein kurzes Kommando oder einen Auftrag selbst rein.
- 🔑 **Nur du** — *eine* Sache kann dir niemand abnehmen: einen Zugangs-Schlüssel erstellen (Schritt 3). Dauert 2 Minuten, wir gehen es Klick für Klick durch.

**8 Schritte.** Navigation: `weiter` · `Schritt X` · `stop`.

> **Ehrlicher Hinweis:** Das klappt selten im ersten Versuch perfekt. Prüfungen sind erst rot, Claude bessert nach, dann grün. Das ist normal — und sogar gut: du *siehst*, dass es wirklich funktioniert, statt es nur zu glauben.

---

## Schritt 1: Worum geht's

Unser Beispiel: eine **Roadmap-Tabelle** in Airtable. Ein Mensch trägt Feature-Ideen ein; eine KI liest sie, bewertet sie und schreibt ihr Urteil zurück. Einfach gesagt: **die Übergabe zwischen Mensch und KI passiert in der Tabelle** — beide arbeiten an denselben Zeilen.

Damit eine KI (oder irgendein Skript) das kann, braucht sie **Zugriff** auf die Tabelle. Airtable hat keinen fertigen Connector — also gehen wir durch die **API** rein, mit einem **Schlüssel**. Genau das bauen wir.

Wenn du das System genauer verstehen willst:
> ⌨️ **Kopier das an Claude:** „Erklär mir in 5 Sätzen, was dieses System tut." *(Claude liest `AIRTABLE_ROADMAP_SPEC.md` für dich.)*

**Reflexion:** Welches System würdest *du* gern anbinden, für das es keinen Connector gibt?

Sag **„weiter"** für Schritt 2.

---

## Schritt 2: Die zwei Dokumente — was gebaut wird und wann's gut ist

Damit Claude den Zugang bauen kann, braucht es zwei kurze Dinge — wie letzte Woche, in **zwei getrennten Dateien**:

| Datei | Was es ist | Frage |
|---|---|---|
| `AIRTABLE_ROADMAP_SPEC.md` | die **Spec** | *Was* soll der Zugriff können? |
| `eval.md` | die **Eval** | *Woran* erkennen wir, dass es funktioniert? |

Beide liegen schon bereit — **du musst sie nicht schreiben.** Überflieg sie kurz. *(Außerdem liegt eine technische Spec `AIRTABLE_ACCESS_SPEC.md` bereit — sie beschreibt die API-Details schon genau und macht den Bau dadurch schneller; lesen musst du sie nicht.)* Wenn's zu lang ist:

> ⌨️ **Kopier das an Claude:** „Fass mir die Spec in 5 Sätzen zusammen und sag, was der Zugriff können muss."

**Reflexion:** Die Eval ist deine Checkliste fürs Abnehmen. Reicht dir „Claude sagt, es geht" — oder willst du es an einer Liste festmachen können?

Sag **„weiter"** für Schritt 3.

---

## Schritt 3: Deine Base und dein Zugangs-Schlüssel (das machst nur du) 🔑

Zwei Dinge richtest **nur du** ein: eine **leere** Airtable-Base und einen Schlüssel dafür. Die Tabelle darin baut **Claude** später für dich (Schritt 6) — du musst kein einziges Feld von Hand anlegen.

### a) Leg eine leere Base an und finde ihre Base-ID

1. Geh auf **airtable.com** → **„+ Create" / „Add a base" → „Start from scratch"**. Eine leere Base erscheint (der kostenlose Plan reicht).
2. **Base-ID finden:** Sie steht in der **Adresszeile deines Browsers**, wenn die Base offen ist:
   ```
   https://airtable.com/appAbCdEf1234567/tblXXXX/viwYYYY
                        └──────┬────────┘
                          die Base-ID
   ```
   Der **erste Teil nach `airtable.com/`**, beginnt mit **`app`**, 17 Zeichen lang. Kopier **nur** diesen `app…`-Block — bis zum nächsten `/`, also **ohne** das `tbl…`/`viw…` dahinter.
   *(Siehst du sie nicht? **Help (?) → API documentation** öffnen — ganz oben steht „The ID of this base is `app…`".)*

> **Die Tabelle heißt `Roadmap` — du legst sie nicht selbst an.** In Airtable lässt du alles, wie es ist (die mitgelieferte „Table 1" ignorierst du oder löschst sie). **Claude** legt in Schritt 6 eine Tabelle namens **`Roadmap`** für dich an.
>
> **Welcher Name kommt in die `.env`? Genau `Roadmap`** — und er steht dort schon vorausgefüllt (`AIRTABLE_TABLE_NAME=Roadmap`, Schritt 4). **Du änderst ihn nicht.** In `.env` füllst du nur **zwei** Dinge aus: deinen **Token** und deine **Base-ID**.

### b) Erstelle deinen Token (PAT)

Drei Begriffe, einfach erklärt:

- **PAT (Personal Access Token)** — ein **Passwort nur für Programme**. Damit darf ein Skript in deinem Namen auf Airtable zugreifen. Du kannst es jederzeit **einzeln zurückziehen**, ohne dein echtes Passwort zu ändern. Es beginnt mit `pat…`. **Das ist das Geheimnis.**
- **Base-ID** — die Adresse deiner Base (aus Schritt a, beginnt mit `app…`). **Kein Geheimnis.**
- **Table-Name** — der Name der Tabelle, hier `Roadmap` (die legt Claude gleich für dich an). **Kein Geheimnis.**

**So erstellst du den PAT — Klick für Klick (ca. 2 Min):**
1. Geh auf **airtable.com/create/tokens** (eingeloggt).
2. **„Create new token"** → gib ihm einen Namen, z. B. „Kurs API".
3. Bei **Scopes** **vier** hinzufügen: `data.records:read`, `data.records:write`, `schema.bases:read`, **`schema.bases:write`**. *(Der letzte erlaubt Claude, die Tabelle für dich anzulegen — sonst geben wir so wenig wie nötig.)*
4. Bei **Access** deine **leere** Base hinzufügen (genau die eine).
5. **„Create token"** → der Token wird **einmal** angezeigt. **Kopier ihn sofort** (du siehst ihn nie wieder).

Halt Token und Base-ID kurz fest. **Zeig den Token niemandem, poste ihn nirgends.**

**Reflexion:** Warum ist ein „Passwort nur für Programme, das man einzeln zurückziehen kann" sicherer, als dem Skript dein echtes Passwort zu geben?

Sag **„weiter"** für Schritt 4.

---

## Schritt 4: Den Schlüssel sicher hinterlegen 🔑🟦

Der Schlüssel kommt jetzt an **einen** Ort — eine Datei namens `.env` —, der **nie geteilt** wird.

🟦 **Claude macht das für dich:**
> ⌨️ **Kopier das an Claude:** „Richte den Arbeitsplatz ein: kopiere `.env.example` zu `.env`, stell sicher dass die `.env` geschützt ist und nicht aus Versehen geteilt wird, und richte die Python-Umgebung ein."

🔑 **Nur du:** Öffne danach die Datei `.env` und füll **zwei** Werte aus: hinter `AIRTABLE_PAT=` deinen echten Token, bei `AIRTABLE_BASE_ID=` deine Base-ID aus Schritt 3. Der dritte Wert **`AIRTABLE_TABLE_NAME=Roadmap` steht schon richtig** — das ist der Name der Tabelle, die Claude für dich anlegt; **lass ihn unverändert.** *(Claude fasst dein Geheimnis nicht an — das machst du selbst.)*

> **🔒 Die eine Sicherheitsregel, die zählt:**
> - Der Token gehört **nur** in `.env`. Diese Datei wird **nie** geteilt, **nie** öffentlich hochgeladen.
> - `.env.example` (ohne echten Token, nur Platzhalter) darf geteilt werden — sie zeigt nur, *welche* Felder gebraucht werden.
> - **Base-ID und Table-Name sind kein Geheimnis** — nur der Token.
> - **Nie** den Token in den Chat kopieren, nie in eine andere Datei, nie posten. Wird er doch mal sichtbar: auf airtable.com einfach **neuen erstellen, alten zurückziehen** — fertig.

**Reflexion:** Es gibt genau ein Geheimnis hier — den Token. Wo darf es liegen, wo nie?

Sag **„weiter"** für Schritt 5.

---

## Schritt 5: Claude baut den Zugang — zuerst die Prüfungen 🟦

Jetzt baut Claude. Der Trick, damit du dem Ergebnis *trauen* kannst: Claude baut **zuerst die Prüfungen** (aus der Eval), dann den Code — und wiederholt, bis **alle Prüfungen grün** sind.

🟦 **Claude macht das** — gib diesen einen Auftrag:
> ⌨️ **Kopier das an Claude:** „Lies `eval.md` und die Spec. Bau den Airtable-Zugang **test-first**: schreib zuerst die Offline-Prüfungen (E1–E7, ohne echtes Airtable), zeig mir, dass sie rot sind, und dann den Code, bis alle grün sind. Leg alles in `build/` ab und führ die Prüfungen selbst aus."

Was du siehst:
1. **Rot** — die Prüfungen existieren, der Code noch nicht. (Gut so.)
2. Claude schreibt den Code, lässt die Prüfungen laufen, bessert nach.
3. **Grün** — alle Prüfungen bestehen.

> **Kein One-Shot — und das ist okay.** Bleibt zwischendrin etwas rot, sag einfach: „die Prüfung ist noch rot, schau dir das an." Claude fixt es. Das Hin und Her *ist* die Arbeit.

**Reflexion:** Was gibt dir mehr Sicherheit — „Claude sagt, es ist fertig" oder „alle Prüfungen sind grün"?

Sag **„weiter"** für Schritt 6.

---

## Schritt 6: Der echte Test — gegen dein Airtable 🟦🔑

Die Prüfungen bis jetzt liefen **ohne** Airtable (sie testen die Logik). Jetzt der Beweis gegen die **echte** Tabelle.

🟦 **Claude macht das — in zwei Mini-Schritten:**

**1) Claude legt deine `Roadmap`-Tabelle an.** Claude erstellt in deiner Base eine Tabelle namens `Roadmap` mit den 8 Feldern — ein API-Call, genau dafür war der Scope `schema.bases:write`:
> ⌨️ **Kopier das an Claude:** „Richte meine Airtable-Tabelle ein: führ `reference/setup_base.py` aus."

**2) Der Live-Test.**
> ⌨️ **Kopier das an Claude:** „Führ `reference/smoke_test.py` gegen meine Base aus — erst nur lesen, danach mit `--write-cycle`."

Du siehst eine Liste mit **Häkchen** ✅: Verbindung steht, alle 8 Felder da, und ein Test-Eintrag wird angelegt, korrekt bewertet und wieder gelöscht. Am Ende eine **Scorecard** mit PASS/FAIL je Kriterium. **Wenn das grün ist, hast du Zugriff.** 🎉

Danach trägt Claude die Ergebnisse in `eval.md` ein — jedes Kriterium von **FAIL auf PASS**, wo der Test grün war. So ist deine Abnahme sichtbar abgehakt, statt nur im Terminal vorbeizurauschen.

> **🔒 Kurz zur Sicherheit:** In den Ausgaben darf der Token **nie** auftauchen. Falls du selbst mal etwas testest: keine „ausführliche" Ausgabe (`-v`) bei solchen Befehlen — da kann der Schlüssel durchrutschen.

**Reflexion:** Warum reicht der Offline-Test nicht — was kann nur die echte Tabelle beweisen?

Sag **„weiter"** für Schritt 7.

---

## Schritt 7: Wenn etwas schiefgeht

Eine rote Meldung ist kein Drama. Meistens einer von drei Gründen — **zeig Claude die Meldung**, dann erklärt und fixt es:

| Meldung | Heißt meistens | Lösung |
|---|---|---|
| `401` / `403` | Schlüssel falsch, abgelaufen oder darf nicht auf die Base | Token prüfen / neu erstellen / Base-Zugriff geben |
| `404` | falsche Base-ID oder falscher Tabellenname | in der Airtable-URL nachschauen |
| `422` / „typecast" | ein Wert passt nicht ins Feld | Claude zeigen — meist ein Einzeiler |

> ⌨️ **Kopier das an Claude:** „Ich bekomme diese Meldung: [einfügen]. Was bedeutet das und wie behebe ich es?"

Faustregel: erst die **Ebene** finden (Schlüssel? Adresse? Code?), dann ansetzen. Ein `401` ist **kein** Code-Fehler.

**Reflexion:** Welche dieser drei Meldungen hat nichts mit dem Code zu tun?

Sag **„weiter"** für Schritt 8.

---

## Schritt 8: Sicher bleiben & übertragen

**Sicher bleiben — in einem Satz:** Der Token ist dein einziges Geheimnis. Er liegt nur in `.env`, wird nie geteilt, und wenn du je unsicher bist, erstellst du auf airtable.com in 30 Sekunden einen neuen und ziehst den alten zurück. *(In diesem Kurs musst du **nichts** veröffentlichen.)*

**Übertragen — das Wichtigste:** Du hast gerade ein System angebunden, für das es **keinen** Connector gibt. Dasselbe Muster funktioniert für fast jedes System mit einer API:
1. Sag, **was** du brauchst (Spec) und **wann's gut ist** (Eval).
2. Hol dir den **Schlüssel** und leg ihn sicher ab.
3. Lass Claude **test-first** bauen und nimm das grüne Ergebnis ab.

**Reflexion:** Welches System bindest du als Nächstes an — und was ist dort das „eine Geheimnis"?

> **Tiefer gehen (optional):** Sag „erklär mir den Code in `reference/`" — dann geht Claude den fertigen Zugang mit dir durch. Oder bau ihn ein zweites Mal selbst, ohne Anleitung.

**Kurs abgeschlossen.** 🎉

---

## Für später

- `AIRTABLE_ROADMAP_SPEC.md` (die Spec) · `eval.md` (die Abnahme) · `AIRTABLE_ACCESS_SPEC.md` (technische Details).
- `reference/` — der fertige Zugang + Prüfungen, als Nachschlagewerk.
