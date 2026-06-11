# Airtable Access — Re-Engineering Specification

> A complete, implementation-agnostic spec for reproducing the Airtable API access
> used in this project (`PM_Workflow`). Hand this file to another project and you can
> recreate byte-for-byte equivalent access — same auth model, same endpoints, same
> request/response shapes, same reliability behavior, same data model.
>
> Reverse-engineered from `03_Scripts/airtable_engine.py`, `check_airtable_schema.py`,
> `upload_roadmap.py`, and verified against the **live base schema** via the Meta API.

---

## 1. What this access actually is

Plain HTTPS calls to the **Airtable Web API v0** using a **Personal Access Token (PAT)**
as a bearer credential. No SDK, no OAuth flow, no MCP server. Just:

- `requests` (Python) → any HTTP client works
- A `.env` file holding three values
- Two host paths: the **data API** and the **metadata API**

If you can send an HTTP request with an `Authorization: Bearer …` header, you can
reproduce 100% of this access in any language.

---

## 2. Prerequisites

| Requirement | Detail |
|---|---|
| **Airtable PAT** | A token starting with `pat…`. Created at <https://airtable.com/create/tokens>. |
| **PAT scopes** | `data.records:read`, `data.records:write`, `schema.bases:read` |
| **PAT base access** | The token must be explicitly granted access to the target base. |
| **HTTP client** | Anything: `requests`, `httpx`, `fetch`, `axios`, `curl`. |

> A token with only `data.records:*` will work for reading/writing rows but will get
> **403/404 on the metadata endpoint** (Section 6.6). Add `schema.bases:read` if you
> need to introspect the schema.

---

## 3. Configuration (the `.env` contract)

Access is fully parameterized by **three** environment variables. Nothing else is
hardcoded.

```dotenv
AIRTABLE_PAT=pat…                 # secret — bearer token, never commit
AIRTABLE_BASE_ID=appcmOMvZGSpCbuSD   # the target base
AIRTABLE_TABLE_NAME=Roadmap          # table name OR table id (tbl…) both work
```

**Concrete target of this project** (identifiers, not secrets — they appear in any
Airtable URL):

| Key | Value |
|---|---|
| Base ID | `appcmOMvZGSpCbuSD` |
| Table name | `Roadmap` |
| Table ID | `tblhhBxZbi9Wb4Aek` |

Load order: read `.env` at startup (`python-dotenv`'s `load_dotenv()` in the original),
fail fast if any of the three are missing.

```python
if not all([api_token, base_id, table_name]):
    raise ValueError("Missing AIRTABLE_PAT / AIRTABLE_BASE_ID / AIRTABLE_TABLE_NAME")
```

---

## 4. Authentication & base URLs

Every request carries:

```
Authorization: Bearer ${AIRTABLE_PAT}
Content-Type: application/json        # required on POST/PATCH; harmless on GET
```

Two URL roots are derived once:

```
DATA URL :  https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}
META URL :  https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables
```

- `{TABLE_NAME}` may be the human name (`Roadmap`) or the table id (`tblhhBxZbi9Wb4Aek`).
  Prefer the **table id** in production — it survives table renames. URL-encode the name
  if it contains spaces.
- A single record is addressed by appending the record id: `{DATA URL}/{RECORD_ID}`
  (record ids look like `rec…`).

---

## 5. Data model (live-verified schema)

Table **`Roadmap`** — 8 fields. Primary field is `Feature Name`.

| # | Field name | Airtable type | API value shape | Allowed values / notes |
|---|---|---|---|---|
| 1 | `Feature Name` | `singleLineText` | string | **Primary field.** Required for create. |
| 2 | `Description` | `richText` | string (Markdown) | Long text with markdown. |
| 3 | `Triad Balance` | `multipleSelects` | array of strings | Subset of `["Brain", "Organs", "Nervous System"]` |
| 4 | `Claude Feedback` | `multilineText` | string | Plain long text. |
| 5 | `Strategy Score` | `number` | number | **precision = 1** (one decimal, e.g. `8.7`). Range used: `1.0`–`10.0`. |
| 6 | `Roadmap_Lane` | `singleSelect` | string | `"Now"`, `"Next"`, `"Later"`, or `""` (blank option exists) |
| 7 | `Status` | `singleSelect` | string | `"Draft"`, `"In Review"`, `"Approved"`, `"UI Ready"`, `"Needs Refinement"`, `"New"`, `"Needs More Information"` |
| 8 | `Horizon` | `singleSelect` | string | `"H1"`, `"H2"`, `"H3"`, `"H1→H2"`, `"H2→H3"` |

**Field-id map** (stable across renames — use these if you address fields by id):

```
Feature Name    fldmtvjNORtIDk2X9   (primaryFieldId)
Description     fldDTE2KawRC2BVHz
Triad Balance   fldKWLpm6W1V6HqQG
Claude Feedback fldSeF0dpiZQCqtKn
Strategy Score  fldikX3fqL5ozy8Cg
Roadmap_Lane    fldKar6FnChAkZtTx
Status          fld1yAE8iOkPCHHRM
Horizon         fldmRKWuLzhmH0CAe
```

### Record envelope

Airtable wraps every row in this structure. Your read code parses it; your write code
produces the `fields` object only.

```json
{
  "id": "recXXXXXXXXXXXXXX",
  "createdTime": "2026-02-03T12:34:56.000Z",
  "fields": {
    "Feature Name": "Universal Invoice Processor",
    "Description": "Plug-and-play invoice processing agent…",
    "Triad Balance": ["Brain", "Nervous System", "Organs"],
    "Strategy Score": 10,
    "Horizon": "H2",
    "Status": "Approved"
  }
}
```

> **Empty fields are omitted.** Airtable does not return keys for blank fields, so always
> read defensively: `fields.get("Status", "")` / `fields?.Status ?? ""`.

---

## 6. Operations

All six operations the original supports, with exact wire format.

### 6.1 List records (with filter + sort)

```
GET {DATA URL}
```

Query parameters (sent as querystring, **bracket notation literal**):

| Param | Example | Meaning |
|---|---|---|
| `filterByFormula` | `OR({Status}='New', {Status}=BLANK())` | Airtable formula filter |
| `sort[0][field]` | `Feature Name` | sort key |
| `sort[0][direction]` | `asc` \| `desc` | sort order |
| `maxRecords` | `5` | cap total returned |
| `pageSize` | `100` | rows per page (max 100) |
| `offset` | `itr…/rec…` | pagination cursor (from previous response) |

**Success** `200`:

```json
{ "records": [ { "id": "rec…", "createdTime": "…", "fields": { … } } ],
  "offset": "itrABC/recDEF" }
```

> ⚠️ **Pagination caveat — the original code does NOT handle this.** Airtable returns at
> most **100 records per page** plus an `offset` token when more exist. The reference
> engine reads only the first page. If your table can exceed 100 rows, loop: keep
> re-requesting with `params["offset"] = response["offset"]` until no `offset` is
> returned. See Section 9 for the corrected loop.

### 6.2 Get one record by id

```
GET {DATA URL}/{RECORD_ID}
```

Returns a single record envelope (Section 5), `200` on success, `404` if not found.

### 6.3 Create record

Two equivalent forms — the project uses **both**:

**Single-record form** (used by `airtable_engine.create_feature`):

```
POST {DATA URL}
Content-Type: application/json

{
  "fields": { "Feature Name": "…", "Description": "…", "Status": "New" },
  "typecast": true
}
```

**Batch form** (used by `upload_roadmap.py`, up to 10 records per call):

```
POST {DATA URL}

{
  "records": [ { "fields": { … } }, { "fields": { … } } ],
  "typecast": true
}
```

Success: `200` (and `201` is also treated as success by the engine). Response echoes the
created record(s) **with their new `id`**.

### 6.4 Update record (partial)

```
PATCH {DATA URL}/{RECORD_ID}

{
  "fields": { "Strategy Score": 8.7, "Status": "Approved", "Roadmap_Lane": "Next" },
  "typecast": true
}
```

`PATCH` = partial update (only listed fields change). Use `PUT` only if you intend to
clear every unlisted field. Success `200`.

### 6.5 Health check

A cheap liveness/credentials probe — list with `maxRecords=1`, 10s timeout:

```
GET {DATA URL}?maxRecords=1   →  200 == healthy
```

### 6.6 Schema introspection (Metadata API)

```
GET https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables
Authorization: Bearer {PAT}
```

Returns all tables with their fields, types, and `options.choices` for select fields.
Requires the `schema.bases:read` scope. This is how the schema in Section 5 was
recovered; use it to regenerate the field map if the base changes.

Relevant response slice:

```json
{ "tables": [ {
  "id": "tblhhBxZbi9Wb4Aek", "name": "Roadmap",
  "primaryFieldId": "fldmtvjNORtIDk2X9",
  "fields": [
    { "id": "fldKWLpm6W1V6HqQG", "name": "Triad Balance", "type": "multipleSelects",
      "options": { "choices": [ {"name": "Brain"}, {"name": "Organs"}, {"name": "Nervous System"} ] } }
  ] } ] }
```

### `typecast` — why it matters

With `"typecast": true`, Airtable coerces loose input into the field's real type:
string `"8"` → number `8`, and **new select-option strings are auto-created** rather than
rejected. Without it, sending a `Status` value that isn't already an option returns
`422 INVALID_MULTIPLE_CHOICE_OPTIONS`. The project sends `typecast: true` on every write.

---

## 7. Reliability & error-handling contract

This is the behavioral core of `_make_request()`. Reproduce it exactly for equivalent
robustness.

**Retry policy** (defaults: `max_retries = 3`, `retry_delay = 1.0s`):

| Condition | Behavior |
|---|---|
| `200` / `201` | Success → return response. |
| `429` Too Many Requests | Read `Retry-After` header (fallback `retry_delay · 2^attempt`), sleep, retry. |
| `4xx` (except 429) | Client error → **do not retry**, return the response so caller can read the error body. |
| `5xx` | Retry with exponential backoff. |
| `Timeout` / `ConnectionError` | Retry with exponential backoff. |
| Retries exhausted | Return `None` (caller treats as hard failure). |

**Backoff formula:** `sleep = retry_delay * (2 ** attempt)` → 1s, 2s, 4s …

**Timeouts:** `30s` for data operations, `10s` for the health check.

**Success codes:** treat both `200` and `201` as success on writes.

**Airtable error envelope** (what you get in `response.text` on failure):

```json
{ "error": { "type": "INVALID_MULTIPLE_CHOICE_OPTIONS",
             "message": "Insufficient permissions to create new select option …" } }
```

Common cases to expect:
- `401 AUTHENTICATION_REQUIRED` — bad/missing PAT.
- `403 NOT_AUTHORIZED` / `INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND` — token lacks scope or base access.
- `404` — wrong base id, table name, or record id.
- `422 INVALID_MULTIPLE_CHOICE_OPTIONS` — select value not in field, and `typecast` off / no permission to create options.
- `429` — rate limit (Airtable caps at **5 requests/sec per base**).

---

## 8. Domain logic layered on top (the "as done here" part)

These conventions are specific to this project's roadmap workflow. Reproduce them only if
you want behavioral parity; they are not part of Airtable itself.

**8.1 "New features" query** — what `get_new_features()` means:

```
filterByFormula = OR({Status}='New', {Status}=BLANK())
sort[0][field]  = Feature Name
sort[0][direction] = asc
```

i.e. rows whose `Status` is literally `New` **or** empty, alphabetized by name.

**8.2 Score → Lane derivation** (`calculate_roadmap_lane`):

| Strategy Score | `Roadmap_Lane` |
|---|---|
| ≥ 9.0 | `Now` |
| 8.0 – 8.9 | `Next` |
| < 8.0 | `Later` |

**8.3 Auto-lane on update:** when an update includes `Strategy Score` but **not**
`Roadmap_Lane`, the engine casts the score to `float` and injects the derived lane before
sending the PATCH. Replicate this if you want updates to keep lane consistent.

---

## 9. Reference implementation (portable skeleton)

A clean, dependency-light reimplementation. Mirrors `airtable_engine.py` but **adds the
missing pagination loop**. Drop-in for any project; swap the domain helpers for your own
schema.

```python
import os, time, requests
from typing import Any, Optional
from dotenv import load_dotenv

class AirtableClient:
    """Schema-agnostic Airtable v0 client with retry/backoff + pagination."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        load_dotenv()
        self.pat        = os.environ["AIRTABLE_PAT"]
        self.base_id    = os.environ["AIRTABLE_BASE_ID"]
        self.table      = os.environ["AIRTABLE_TABLE_NAME"]
        self.max_retries, self.retry_delay = max_retries, retry_delay
        self.data_url = f"https://api.airtable.com/v0/{self.base_id}/{self.table}"
        self.meta_url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"
        self.headers  = {"Authorization": f"Bearer {self.pat}",
                         "Content-Type": "application/json"}

    def _request(self, method: str, url: str, **kw) -> Optional[requests.Response]:
        for attempt in range(self.max_retries):
            try:
                r = requests.request(method, url, headers=self.headers, **kw)
                if r.status_code in (200, 201):
                    return r
                if r.status_code == 429:
                    wait = int(r.headers.get("Retry-After", self.retry_delay * 2**attempt))
                    time.sleep(wait); continue
                if 400 <= r.status_code < 500:          # client error → don't retry
                    return r
            except (requests.Timeout, requests.ConnectionError):
                pass
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * 2**attempt)
        return None

    # ---- reads --------------------------------------------------------------
    def list_records(self, *, formula=None, sort_field=None, sort_dir="asc",
                     max_records=None) -> list[dict]:
        params, out, offset = {}, [], None
        if formula:    params["filterByFormula"] = formula
        if sort_field: params.update({"sort[0][field]": sort_field,
                                      "sort[0][direction]": sort_dir})
        if max_records: params["maxRecords"] = max_records
        while True:                                     # ← pagination the original lacks
            if offset: params["offset"] = offset
            r = self._request("GET", self.data_url, params=params, timeout=30)
            if not r or r.status_code != 200: break
            body = r.json()
            out.extend(body.get("records", []))
            offset = body.get("offset")
            if not offset or (max_records and len(out) >= max_records): break
        return out

    def get_record(self, rec_id: str) -> Optional[dict]:
        r = self._request("GET", f"{self.data_url}/{rec_id}", timeout=30)
        return r.json() if r and r.status_code == 200 else None

    # ---- writes -------------------------------------------------------------
    def create(self, fields: dict, typecast=True) -> Optional[str]:
        r = self._request("POST", self.data_url, timeout=30,
                          json={"fields": fields, "typecast": typecast})
        return r.json().get("id") if r and r.status_code in (200, 201) else None

    def update(self, rec_id: str, fields: dict, typecast=True) -> bool:
        r = self._request("PATCH", f"{self.data_url}/{rec_id}", timeout=30,
                          json={"fields": fields, "typecast": typecast})
        return bool(r and r.status_code == 200)

    # ---- ops ----------------------------------------------------------------
    def health(self) -> bool:
        r = self._request("GET", self.data_url, params={"maxRecords": 1}, timeout=10)
        return bool(r and r.status_code == 200)

    def schema(self) -> Optional[dict]:
        r = self._request("GET", self.meta_url, timeout=30)
        return r.json() if r and r.status_code == 200 else None
```

**JavaScript/TypeScript equivalent** (same contract, `fetch`-based):

```ts
const BASE = process.env.AIRTABLE_BASE_ID!;
const TABLE = process.env.AIRTABLE_TABLE_NAME!;
const dataUrl = `https://api.airtable.com/v0/${BASE}/${encodeURIComponent(TABLE)}`;
const headers = {
  Authorization: `Bearer ${process.env.AIRTABLE_PAT!}`,
  "Content-Type": "application/json",
};

async function listRecords(formula?: string) {
  const out: any[] = []; let offset: string | undefined;
  do {
    const u = new URL(dataUrl);
    if (formula) u.searchParams.set("filterByFormula", formula);
    if (offset)  u.searchParams.set("offset", offset);
    const r = await fetch(u, { headers });          // add 429/Retry-After backoff in prod
    const body = await r.json();
    out.push(...(body.records ?? []));
    offset = body.offset;
  } while (offset);
  return out;
}

const updateRecord = (id: string, fields: Record<string, unknown>) =>
  fetch(`${dataUrl}/${id}`, { method: "PATCH", headers,
    body: JSON.stringify({ fields, typecast: true }) });
```

---

## 10. Known limitations of the original (fix these in the rebuild)

1. **No pagination** — reads stop at 100 rows. Fixed in §9 with the `offset` loop.
2. **No batch limit guard** — Airtable caps create/update at **10 records per call**;
   the batch uploader happens to send 10. Chunk larger payloads.
3. **No client-side rate limiting** — only reactive `429` handling. Airtable's hard limit
   is **5 req/s per base**; add a small throttle for high-volume jobs.
4. **Secrets in `.env` only** — fine locally; use a secret manager in CI/prod and never
   commit the PAT.
5. **Table addressed by name** — renaming the table breaks access. Prefer the table id
   `tblhhBxZbi9Wb4Aek`.

---

## 11. Acceptance tests (prove parity)

Re-implementation is correct when all pass against the live base:

- [ ] **Health:** `GET {DATA URL}?maxRecords=1` → `200`.
- [ ] **Schema:** Meta API returns table `Roadmap` with the 8 fields of §5.
- [ ] **List+filter:** `OR({Status}='New', {Status}=BLANK())` returns only New/blank rows, name-sorted.
- [ ] **Get:** fetching a known `rec…` id returns its envelope; bad id → `404`/`None`.
- [ ] **Create:** POST a `{Feature Name, Description}` row → returns a new `rec…` id.
- [ ] **Update:** PATCH `Strategy Score = 8.7` → row shows `8.7` and (if auto-lane on) `Roadmap_Lane = "Next"`.
- [ ] **Typecast:** writing a brand-new `Status` string succeeds with `typecast:true`, and (option-create permission absent) fails `422` without it.
- [ ] **Rate limit:** burst >5 req/s → at least one `429` that is transparently retried and ultimately succeeds.

---

### Appendix A — curl smoke tests

```bash
set -a; source .env; set +a

# health / list one
curl -s "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_TABLE_NAME?maxRecords=1" \
  -H "Authorization: Bearer $AIRTABLE_PAT"

# schema
curl -s "https://api.airtable.com/v0/meta/bases/$AIRTABLE_BASE_ID/tables" \
  -H "Authorization: Bearer $AIRTABLE_PAT"

# create
curl -s -X POST "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_TABLE_NAME" \
  -H "Authorization: Bearer $AIRTABLE_PAT" -H "Content-Type: application/json" \
  -d '{"fields":{"Feature Name":"Smoke Test","Description":"hello","Status":"New"},"typecast":true}'

# update (replace recXXX)
curl -s -X PATCH "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_TABLE_NAME/recXXX" \
  -H "Authorization: Bearer $AIRTABLE_PAT" -H "Content-Type: application/json" \
  -d '{"fields":{"Strategy Score":8.7,"Status":"Approved"},"typecast":true}'
```
