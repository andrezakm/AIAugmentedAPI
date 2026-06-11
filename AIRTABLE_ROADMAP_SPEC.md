# The Roadmap Store — Requirements-Driven Specification

> **What this is.** A specification for the persistent roadmap store at the centre of the
> NeoEmployee PM Workflow, written *forward from the requirements* rather than backward
> from the code. It starts with what the system is trying to do (as documented across the
> `.md` files), derives what the store must therefore be able to do, and only then arrives
> at the concrete Airtable access. A developer on another project should be able to read
> this and rebuild the same capability — and understand *why* every field and every call
> exists.
>
> **Companion document.** [AIRTABLE_ACCESS_SPEC.md](AIRTABLE_ACCESS_SPEC.md) is the
> bottom-up technical reference (exact endpoints, headers, JSON, retry contract). This
> document is the top-down *why*. Where they overlap they agree; where you need wire
> detail, follow the link.
>
> **Sources.** Derived from `.claude/project.md`, `.claude/skills/audit/SKILL.md`,
> `.claude/skills/strategic-review/SKILL.md`, `03_Scripts/strategic-roadmap-review-prompt.md`,
> and the strategy context in `02_Resources/context/{company,markers,horizons,market}.md`.

---

## 1. The system in one paragraph

NeoEmployee sells "AI employees": bespoke first, productized once 2–3 clients want the
same thing. The PM Workflow is the machine that runs that strategy day to day. Feature
ideas ("we could build an *Insurance Claims Parser*") enter a **roadmap**; an AI auditor
scores each one against a fixed strategy framework, sorts it into a priority lane, and
either approves it (producing a prototype and a stakeholder email) or hands it back with
specific questions. A second AI analyst periodically reads the whole roadmap and stress-
tests it against operational reality (team capacity, cash flow, focus). **The roadmap
itself is the shared state both the humans and the AIs work on.** This spec is about that
shared state: what it must be, and how code reaches it.

---

## 2. The central requirement (everything else follows from this)

> **The roadmap is simultaneously a human artifact and a machine artifact, edited
> asynchronously by both parties, and it is the only handoff channel between them.**

A human product manager needs to *drop in* a rough feature idea, later *refine* a
description, and *read* the AI's verdict — in a comfortable, spreadsheet-like UI, with no
code. An AI agent needs to *find* the ideas waiting for it, *write back* a structured
verdict, and *re-read* the human's refinements on the next pass — over an HTTP API, with no
human in the loop. Neither side uses the other's tools. They meet only in the store.

That single requirement forces almost everything below: a hosted store (not a local file),
a human grid UI *and* a REST API over the *same* records, a controlled shared vocabulary so
both sides mean the same thing by "Approved", a per-record stable identity so an update
doesn't clobber a human's parallel edit, and a status field that behaves as a state
machine. Airtable is the chosen realization because it provides all of these out of the
box (§7).

---

## 3. Actors and how they interact through the store

The scripts never call each other directly. They interact **only by reading and writing
roadmap records.** The store is the bus.

```
                          ┌───────────────────────────────────┐
   human PM (grid UI) ───►│                                   │
   • adds suggestions     │        THE ROADMAP STORE          │
   • refines descriptions │   (one record per feature idea)   │◄─── seeding script
   • reads verdicts       │                                   │     upload_roadmap.py
   • tweaks fields        │   fields: name, description,       │     (bulk create)
                          │   status, score, lane, triad,     │
        ┌─────────────────│   horizon, claude-feedback        │
        │   reads "New"    │                                   │
        ▼   writes verdict └───────────────────────────────────┘
   ┌──────────┐                    ▲ reads ALL          
   │  /audit  │  per feature,       │ (read-only)        
   │ auditor  │  read+write         │                    
   └────┬─────┘                ┌────┴───────────┐        
        │ approved (≥8.0)      │ /strategic-    │        
        ▼                      │ review analyst │        
   prototype HTML +            └────┬───────────┘        
   stakeholder email                ▼                    
   (04_Outputs/…)              markdown report           
                               (04_Outputs/outbox/…)     
```

| Actor | Role | What it needs from the store | Access |
|---|---|---|---|
| **Human PM** | Owns the ideas and the refinements | Direct, friendly editing of any field; sees AI output inline | Native UI (grid) |
| **Seeding** (`upload_roadmap.py`) | Loads an initial/batch set of ideas | Create many records in one go | **Create** (batch) |
| **`/audit`** (Auditor) | Evaluates and iterates on *individual* suggestions | Find unprocessed ideas; write a structured verdict back to the exact record | **Read filtered + Update by id** |
| **`/strategic-review`** (Analyst) | Stress-tests the *whole portfolio* | Read every record, grouped by lane | **Read all (read-only)** |

**Out of scope but worth naming:** the `Workspace_Publisher` / `Workspace_Puller` scripts
sync long-form documents (PRDs) to **Google Docs**, and the `zero-to-roadmap` pipeline turns
interviews into PRDs as **local files**. Those are *sibling* integrations. They do not touch
the roadmap store. This spec covers only the roadmap store.

---

## 4. The feature lifecycle (the "iteration on suggestions" loop)

This is the heart of the system and the reason the store must behave as a **state machine**
with a **dialogue channel**. A feature suggestion is not entered once and scored once; it
*cycles* between the human and the auditor until it is good enough to approve or is parked.

```
   (human or seeding creates a record)
                │
                ▼
        ┌───────────────┐
        │ Status = New  │  ◄─────────────────────────────────┐
        │  (or empty)   │                                    │
        └───────┬───────┘                                    │
                │   /audit picks it up                       │ human improves the
                ▼                                            │ Description and the
        ┌─────────────────────┐                              │ record returns to the
        │  QUALITY GATE        │  description complete?       │ auditor's "New" queue
        └───────┬─────────────┘                              │  (re-audit)
        insufficient │ sufficient                            │
                ▼    ▼                                        │
   ┌──────────────────────┐   ┌──────────────────────┐       │
   │ Needs More           │   │   SCORING            │       │
   │ Information          │   │ Triad 30 / Markers 40 │       │
   │ score ≤ 7.5 (capped) │   │ / Strategic 30 → X.X  │       │
   │ + clarifying Qs in   │   └─────────┬─────────────┘       │
   │   Claude Feedback    │             │                     │
   └──────────┬───────────┘   ┌─────────┴──────────┐          │
              │           <8.0 │                    │ ≥8.0     │
              └────────────────┤                    ▼          │
                               ▼          ┌────────────────────┴──┐
                    ┌────────────────────┐│  Status = Approved     │
                    │ Needs Refinement   ││  lane = Now (≥9) /      │
                    │ marker-cited        ││         Next (8–8.9)    │
                    │ feedback, lane=Later││  + prototype + email    │
                    └─────────┬──────────┘└────────────────────────┘
                              │
                              └──────────► back to the human ──────┘
```

Three things the store must support to make this loop work:

1. **A status that is a controlled state machine** — only a known set of states, so the
   auditor can query "everything in `New`" and the human can see "this one is waiting on
   me (`Needs More Information`)". Free-text status would break the queue.
2. **A persistent feedback channel** — `Claude Feedback` carries the AI's *reasoning and
   its questions* back to the human, in the same record as the data. The loop is a
   conversation; the field is the conversation.
3. **Stable per-record identity** — re-auditing must update *the same* record the human
   refined, not create a duplicate. (Airtable record ids; §8, §9.)

---

## 5. The strategy framework the fields encode

The fields are not arbitrary columns; each one captures a dimension of NeoEmployee's
documented strategy. To rebuild the store faithfully you must know what each dimension
*means*, because that meaning constrains the field's type and allowed values.

- **The Triad** (`company.md`) — every agent balances **Brain** (LLM reasoning),
  **Nervous System** (n8n integration/orchestration), **Organs** (APIs, DBs, parsers).
  Not every feature needs all three; the *roadmap* needs balance across them. → a
  **multi-value** field whose vocabulary is exactly these three.
- **Markers M1–M7** (`markers.md`) — identity constraints. Especially **M2** (reuse beats
  reinvention), **M3** (technical not domain experts; co-dependent with clients), **M6**
  (no military — a hard refusal), **M7** (no high-maintenance; products work Day 1).
  These drive *scoring and approval*, not a field of their own; they surface as cited
  reasoning inside `Claude Feedback`.
- **Three Horizons** (`horizons.md`) — **H1** bespoke (funds the company), **H2**
  plug-and-play agents (scale), **H3** end-to-end process products. H1 funds H2 funds H3.
  → a **single-choice** field, plus transition states (`H1→H2`, `H2→H3`).
- **Scoring rubric** (`project.md`, `audit/SKILL.md`) — Overall = Triad×30% + Markers×40%
  + Strategic×30%, expressed to **one decimal**. → a **numeric** field with fixed precision.
- **Prioritization rule** — score maps deterministically to a lane: ≥9.0 → *Now*, 8.0–8.9
  → *Next*, <8.0 → *Later*. → a **single-choice** lane field, *derived* (not hand-entered).
- **Quality gate** — a description that doesn't answer What/How/Who/Problem/Components
  caps the score at **7.5** and parks the feature in `Needs More Information`. → a business
  rule the writer enforces, not a field.

---

## 6. Derived requirements for the store

Each requirement is traced to the actor need or strategy rule that forces it. A faithful
re-implementation must satisfy all of them.

| # | Requirement | Why (driven by) |
|---|---|---|
| **R1** | One **record per feature suggestion**, holding all of its state | §3 — the store is the unit of handoff |
| **R2** | A **human-editable UI** over the same records the API sees | §2 — human drops/refines ideas without code |
| **R3** | **Controlled vocabularies** for status, lane, horizon, triad (no free text where a state machine is needed) | §4 — auditor queues by status; both sides share meaning |
| **R4** | A **numeric score to one decimal place** | §5 — scoring rubric precision rule |
| **R5** | **Find only unprocessed suggestions** — query "Status = New or empty", sorted deterministically | §3 `/audit` queue; §4 re-audit returns refined items here |
| **R6** | **Read the entire portfolio** in one pass, grouped by lane | §3 `/strategic-review` reads all, read-only |
| **R7** | **Update a single record by stable id**, changing only named fields, without disturbing the human's other edits | §4 the iteration loop must not duplicate or clobber |
| **R8** | **Create** records — one at a time (auditor/test) and in **batches** (seeding) | §3 seeding; ad-hoc idea capture |
| **R9** | A **dialogue field** that round-trips AI reasoning/questions to the human | §4 `Claude Feedback` is the conversation |
| **R10** | **Lane is derived from score on write**, not entered by hand | §5 prioritization rule; keeps lane/score consistent |
| **R11** | **Lenient type coercion on write** — string `"8"` → number `8`, new option strings accepted — so writers don't have to pre-validate every select value | §5 status/horizon/triad vocabularies evolve; auditor writes them as plain strings |
| **R12** | **Resilient to transient failure** — retry with backoff, respect rate limits, never block the workflow on a blip | `project.md` error-handling policy ("don't block on transient errors") |
| **R13** | **Simple machine auth** that one shared base grants to a script, plus optional **schema read** for introspection | §3 a headless agent must authenticate without a human OAuth dance |
| **R14** | **Config, not hardcoding** — which base/table to hit is environment-driven | portability across environments / re-use in another project |

---

## 7. Why Airtable satisfies these (the integration choice)

A plain local file fails R2 (no shared UI), R3 (no enforced vocabulary), R7 (no record
identity / safe concurrent edits). A bare SQL database fails R2 (no friendly UI for a
non-engineer PM). A full SaaS PM tool (Jira/Linear) over-constrains R3/R5 with opinionated
workflows and is heavier to script.

**Airtable hits the whole set:** a hosted base presents a **grid UI** to the human (R2) and
a **REST API** over the *same rows* to the script (R1, R5–R8); native **single-select /
multi-select / number** field types give enforced **controlled vocabularies and decimal
precision** (R3, R4); every row has a **stable record id** for safe partial updates (R7);
**`typecast`** provides lenient write coercion (R11); a **Personal Access Token** gives
dead-simple headless auth with optional **schema scope** (R13); and the base/table are just
**ids in config** (R14). R10 and R12 aren't Airtable features — they live in the access
layer the script wraps around the API (§9, §10).

> The trade-off accepted: Airtable enforces *field-level* vocabularies but **not** the
> *state-machine transitions* (it will happily let anything move to any status) and **not**
> the lane-from-score rule. Those invariants are enforced **client-side** by the access
> layer and the skills. Re-implementations must carry that responsibility (§10).

---

## 8. The data model (derived, then pinned to the realized values)

From §5–§6, the store needs exactly these columns. The right column shows how the running
system actually realizes each one (the concrete vocabulary you should reproduce to talk to
*this* base; verify live via the schema endpoint in §9.6).

| Field (logical) | Requirement | Realized type & vocabulary |
|---|---|---|
| **Feature Name** | R1 identity (human-readable), primary | `singleLineText` — the primary field |
| **Description** | R4/quality-gate input; the thing the human refines | `richText` (Markdown long text) |
| **Status** | R3 + R5 state machine / queue | `singleSelect`: `New`, `Needs More Information`, `Needs Refinement`, `Approved`, `Draft`, `In Review`, `UI Ready` |
| **Strategy Score** | R4 decimal score | `number`, **precision = 1** (e.g. `8.7`); range used 1.0–10.0 |
| **Roadmap_Lane** | R10 derived priority | `singleSelect`: `Now`, `Next`, `Later` (+ blank) |
| **Triad Balance** | §5 Triad, multi-valued | `multipleSelects`: `Brain`, `Nervous System`, `Organs` |
| **Horizon** | §5 Three Horizons | `singleSelect`: `H1`, `H2`, `H3`, `H1→H2`, `H2→H3` |
| **Claude Feedback** | R9 dialogue channel | `multilineText` |

**Concrete target** (identifiers, not secrets — they appear in any Airtable URL; reproduce
to reach the same base):

```
Base   : appcmOMvZGSpCbuSD
Table  : Roadmap   (id tblhhBxZbi9Wb4Aek, primary field = Feature Name)
```

> **Empty fields are not returned by the API.** Because Airtable omits blank fields, "Status
> is empty" and "Status = New" are *both* the unprocessed state (R5). Always read
> defensively (`fields.get('Status', '')`).

---

## 9. The access contract (operations derived from actor needs)

Configuration is environment-driven (R14). Three values, nothing else hardcoded:

```dotenv
AIRTABLE_PAT=pat…                 # secret bearer token (scopes below) — never commit
AIRTABLE_BASE_ID=appcmOMvZGSpCbuSD
AIRTABLE_TABLE_NAME=Roadmap       # name or table id
```

**Auth (R13).** Every call sends `Authorization: Bearer ${AIRTABLE_PAT}`. The token needs
`data.records:read` + `data.records:write` for the roadmap operations, and
`schema.bases:read` if you use the introspection call (§9.6). The token must be granted
access to the base.

The six operations below are *derived from* the actor needs — each one exists because an
actor in §3 requires it. Exact wire format (URLs, status codes, JSON bodies) is in the
[companion access spec](AIRTABLE_ACCESS_SPEC.md); here we state purpose, shape, and the
requirement it serves.

### 9.1 Fetch the unprocessed queue — *for the Auditor* (R5)
The auditor must pull exactly the suggestions waiting for it, in a stable order.
- `GET` the table with `filterByFormula = OR({Status}='New', {Status}=BLANK())`, sorted by
  `Feature Name` ascending.
- Returns the records the audit loop iterates over. Re-audited (human-refined) items
  reappear here automatically once their status is back to `New`/blank.

### 9.2 Fetch the whole portfolio — *for the Analyst* (R6)
The strategic review reads **everything**, then groups by `Roadmap_Lane` in memory.
- `GET` the table (optionally sorted), **read-only** — the analyst never writes back.
- ⚠️ **Must page through all results.** Airtable returns ≤100 rows per page plus an
  `offset`; loop until no `offset`. (The original engine reads only the first page — a real
  bug once the roadmap exceeds 100 features. Fix it here.)

### 9.3 Get one feature by id — *validation/refresh* (R7)
- `GET` the table with the record id appended. Used to confirm a record exists before
  updating, or to refresh one feature.

### 9.4 Create a feature — *for seeding and ad-hoc capture* (R8)
- `POST` with a `fields` object (single) or a `records[]` array (batch, **≤10 per call** —
  chunk larger seeds). Send `typecast: true` (R11). Returns the new record id(s).

### 9.5 Update a feature's verdict — *for the Auditor* (R7, R9, R10, R11)
The write that closes each audit pass.
- `PATCH` the record by id with only the changed fields:
  `Strategy Score`, `Roadmap_Lane`, `Status`, `Triad Balance` (array), `Horizon`,
  `Claude Feedback`. Send `typecast: true`.
- `PATCH` (not `PUT`) so the human's untouched fields are preserved (R7).
- The access layer derives `Roadmap_Lane` from `Strategy Score` before sending if the
  caller didn't supply it (R10, §10).

### 9.6 Read the schema — *introspection / regeneration* (R3 maintenance)
- `GET` the metadata endpoint for the base to list tables, field types, and select
  `choices`. This is how the realized vocabularies in §8 are recovered when the base
  changes. Requires `schema.bases:read`.

---

## 10. Invariants the access layer must enforce (not the database)

Airtable stores values; it does **not** enforce the system's business rules. A faithful
re-implementation must enforce these in the client wrapper, exactly as the skills + engine
do today:

1. **Lane follows score (R10).** On any write that sets `Strategy Score` without an explicit
   `Roadmap_Lane`: cast the score to float, then set lane = `Now` (≥9.0) / `Next` (8.0–8.9)
   / `Later` (<8.0). Keeps the two fields from drifting apart.
2. **Quality-gate cap.** An insufficient description ⇒ `Status = Needs More Information`,
   `Strategy Score ≤ 7.5`, lane `Later`, and clarifying questions written into
   `Claude Feedback`. (Enforced by the auditor before it writes.)
3. **Decimal precision (R4).** Scores are always one decimal place.
4. **Marker hard-stops.** Never approve a feature that violates **M6** (military) or that is
   inherently **M7** high-maintenance — regardless of score.
5. **Status stays in the controlled set (R3).** Writers only emit known status values; this
   is what keeps the §9.1 queue query meaningful.
6. **Typecast on every write (R11).** So plain-string select values and stringified numbers
   are coerced rather than rejected (a `422` otherwise).
7. **Resilience (R12).** Retry with exponential backoff; on `429` honor `Retry-After`; do
   not retry other `4xx`; surface a failure after retries are exhausted but **don't block**
   the rest of the workflow.

---

## 11. Acceptance criteria (a rebuild is correct when…)

Phrased as requirements so another project can check itself:

- [ ] **R1/R2** A human can open the base in a grid and add a row; the API sees it
      immediately, and vice-versa.
- [ ] **R5** The auditor query returns *only* features whose `Status` is `New` or empty,
      name-sorted, and nothing else.
- [ ] **R6** The analyst read returns **every** feature even when the table exceeds 100 rows
      (pagination proven), and performs **no writes**.
- [ ] **R7** Updating a feature changes only the named fields on the *same* record id; a
      human edit to an untouched field survives the write.
- [ ] **R8** Seeding creates N features (batched ≤10/call) and each comes back with a record
      id.
- [ ] **R9** `Claude Feedback` written by the auditor is readable by the human in the UI and
      on the next API read.
- [ ] **R10** Writing `Strategy Score = 8.7` with no lane results in `Roadmap_Lane = Next`;
      `9.2` ⇒ `Now`; `7.5` ⇒ `Later`.
- [ ] **R3/R11** Writing a status string with `typecast:true` succeeds; the same write with
      typecast off and a brand-new option fails `422` (proving the vocabulary boundary).
- [ ] **R12** A burst over Airtable's ~5 req/s/base limit produces a `429` that is
      transparently retried and ultimately succeeds.
- [ ] **State machine** A feature can travel `New → Needs More Information →` (human refines)
      `→ New → Approved` without ever duplicating the record.

---

## 12. What this spec deliberately excludes

So boundaries are clear when you port it:

- **Google Docs sync** (`Workspace_Publisher/Puller`, `.agent/scripts/*.js`) — a separate
  integration via the google-workspace MCP, unrelated to the roadmap store.
- **The upstream discovery pipeline** (`zero-to-roadmap`: interviews → pain points → PRD →
  press release → story map) — produces *local files*; it feeds ideas to humans, who then
  enter roadmap suggestions. It does not write to the store.
- **Prototype and email generation** — downstream *consumers* of an `Approved` verdict; they
  read the audit result and emit files under `04_Outputs/`, but impose no new store
  requirements beyond reading a feature.
- **The wire-level mechanics** — see [AIRTABLE_ACCESS_SPEC.md](AIRTABLE_ACCESS_SPEC.md).
