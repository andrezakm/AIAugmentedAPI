# Handover — Airtable Roadmap Store Access

**Purpose.** Everything another project needs to reproduce the Airtable access used in the
NeoEmployee PM Workflow: read feature suggestions from a roadmap, write back AI verdicts
(score / lane / status / feedback), and read the whole portfolio for analysis. Self-
contained — drop this folder into the new project and go.

**Author's note.** This is a clean re-packaging of a working integration. The reference
client below is not pseudo-code; it runs against the live base and fixes two latent bugs
in the original (see *Gotchas*). Start with this README, then read the specs as needed.

---

## What you're receiving

```
handover/
├── README.md                  ← you are here (start)
├── AIRTABLE_ROADMAP_SPEC.md   ← the WHY: requirements-driven spec (read first for understanding)
├── AIRTABLE_ACCESS_SPEC.md    ← the HOW: wire-level reference (endpoints, JSON, retry contract)
├── .env.example               ← config template (copy to .env, add your PAT)
└── reference/
    ├── airtable_client.py     ← drop-in client implementing the whole contract
    ├── smoke_test.py          ← runnable acceptance checks (spec §11)
    └── requirements.txt        ← requests + python-dotenv
```

Read order: **this README** → [AIRTABLE_ROADMAP_SPEC.md](AIRTABLE_ROADMAP_SPEC.md) (the model
and the *why*) → [AIRTABLE_ACCESS_SPEC.md](AIRTABLE_ACCESS_SPEC.md) (only when you need exact
wire detail) → [`reference/airtable_client.py`](reference/airtable_client.py) (the code).

---

## 5-minute quickstart

```bash
cd handover
cp .env.example .env                 # then edit .env and paste your AIRTABLE_PAT

python3 -m venv .venv && source .venv/bin/activate
pip install -r reference/requirements.txt

# read-only acceptance run (safe against the live base):
python reference/smoke_test.py

# include a create→update→delete round-trip (uses a temp, self-deleting record):
python reference/smoke_test.py --write-cycle
```

Then in your own code:

```python
import sys; sys.path.insert(0, "reference")
from airtable_client import AirtableRoadmap

rm = AirtableRoadmap()                       # reads AIRTABLE_* from .env / env
for rec in rm.get_new_features():            # the unprocessed queue
    rm.update_feature(rec["id"], {           # write a verdict back to the same record
        "Strategy Score": 8.7,               # → Roadmap_Lane auto-set to "Next"
        "Status": "Approved",
        "Claude Feedback": "Strong M2 reuse, clean triad…",
        "Triad Balance": ["Brain", "Organs"],
        "Horizon": "H1→H2",
    })
```

---

## The access model in 60 seconds

- **Transport:** plain HTTPS to the Airtable Web API v0. No SDK.
- **Auth:** one Personal Access Token (`pat…`) as `Authorization: Bearer …`. Scopes:
  `data.records:read`, `data.records:write`, and `schema.bases:read` for introspection.
- **Config:** three env vars — `AIRTABLE_PAT`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`.
- **Two URL roots:** `…/v0/{base}/{table}` for rows, `…/v0/meta/bases/{base}/tables` for schema.
- **Operations:** list-with-filter, list-all (paginated), get-by-id, create (single + batch ≤10),
  update-by-id (PATCH, partial), delete, health, schema.
- **The store is the handoff bus:** humans edit rows in Airtable's grid UI; scripts read/write
  the same rows over the API. `Status` is a state machine; `Claude Feedback` is the dialogue
  channel between the AI and the human. See the requirements spec for the full rationale.

### Data model (table `Roadmap`)

| Field | Type | Values |
|---|---|---|
| Feature Name | singleLineText | primary |
| Description | richText | markdown |
| Status | singleSelect | New · Needs More Information · Needs Refinement · Approved · Draft · In Review · UI Ready |
| Strategy Score | number (1 decimal) | 1.0–10.0 |
| Roadmap_Lane | singleSelect | Now · Next · Later (derived from score) |
| Triad Balance | multipleSelects | Brain · Nervous System · Organs |
| Horizon | singleSelect | H1 · H2 · H3 · H1→H2 · H2→H3 |
| Claude Feedback | multilineText | AI reasoning / questions back to the human |

---

## Gotchas (the non-obvious stuff that bites)

1. **Pagination is mandatory for full reads.** Airtable returns ≤100 rows/page + an `offset`.
   The original engine read only the first page; `get_all_features()` here loops until done.
   If you re-implement, don't skip this — it silently truncates once the table passes 100.
2. **Batch writes cap at 10 records/call.** `create_many()` chunks automatically; a naive
   loop sending 50 in one POST gets a `422`.
3. **Rate limit: ~5 requests/sec per base.** Exceed it → `429`. The client retries with
   backoff and honors `Retry-After`; for big jobs add your own throttle.
4. **`typecast: true` on every write.** Lets you send select values and scores as plain
   strings; without it a brand-new option value returns `422 INVALID_MULTIPLE_CHOICE_OPTIONS`.
5. **Empty fields are omitted from responses.** "Status missing" and "Status = New" are both
   the unprocessed state. Always read defensively (`fields.get("Status", "")`).
6. **Lane derivation lives in the client, not Airtable.** Airtable won't compute
   `Roadmap_Lane` from `Strategy Score`; `update_feature()` does it before sending.
7. **Use `PATCH`, not `PUT`.** PATCH preserves the human's untouched fields; PUT clears them.
8. **Secrets:** the PAT is the only secret here — keep it in `.env` (git-ignored), never commit
   it. Base/table ids are not secret. Rotate the PAT if it ever leaks.

---

## Pointing at a different base

To reuse the *pattern* against your own roadmap rather than the original base: create the
table with the fields above (or run `get_schema()` against this base to copy the exact
field/option definitions), then set `AIRTABLE_BASE_ID` / `AIRTABLE_TABLE_NAME` in `.env`.
Nothing else changes.

---

## Acceptance criteria

`reference/smoke_test.py` checks the spec's acceptance list (§11 of the requirements spec):
health, schema shape, the unprocessed-queue filter, full paginated read, lane-from-score,
and an optional create→update→verify→delete cycle. A correct rebuild passes all of them.

---

## Provenance

The two specs cite source files (`02_Resources/context/*.md`, `.claude/skills/*`, etc.) from
the **original** PM_Workflow repo for traceability; those relative paths resolve there, not
inside this handover folder. The schema and field options were captured live from the base's
metadata API, not guessed.
