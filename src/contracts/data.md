# Data layer contract

Version 1. Design contract, no runtime serializer or validator is implemented yet.
Companion to `src/contracts/analysis.md`, which defines the analysis input and
result. This file defines what the data layer stores and hands to consumers.

Execution constraint: there is no server and no SQLite in the bundle. The only
runnable store is the splash `fs` API (JSON files, 8 MB quota). Everything below
is files, not tables. `src/data/` holds contracts and deterministic helpers;
runnable ingestion lives in `bundle/main.splash` until the integrator moves it.

## File layout

| File | Owner | Content |
| --- | --- | --- |
| `cache_<source>.json` | ingestion | Latest fetched rows per source (`hn`, `techmeme`, `google`, `weather`, `hefeng`, `hefeng_warn`) |
| `saved.json` | app | Bookmarked rows (existing pattern) |
| `interests.json` | data | User watches (see §3) |
| `schedules.json` | app | In-app schedule items with `version` (see §4) |
| `suggestions.json` | data | Suggestion records with `status` (see §5) |
| `meta.json` | data | `{schema_version: 1}` |

Disposable caches (`cache_*`) are separate from user records (`interests`,
`schedules`, `suggestions`). Never delete user records on a parse error; fall
back to in-memory state and surface a diagnosable notice.

## Row shape (feed cache)

Every `cache_<source>.json` is an array of rows in the feed shape used by
`bundle/main.splash`:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `title` | string | yes | Non-empty headline or day summary |
| `link` | string | yes | Absolute source URL, tracking params stripped |
| `source` | string | yes | Display name, never lost through dedup |
| `published` | int | yes | Unix seconds. Fetch time when the true publication time is unknown |
| `summary` | string | no | Source summary, never rewritten |
| `day` | string | no | `YYYY-MM-DD` forecast valid date (weather rows only) |
| `image`, `discussion`, `points`, `comments` | mixed | no | Source-native extras |

`published` follows the existing feed convention (Unix seconds, see `ago()`).
The analysis adapter converts to RFC 3339 at the boundary. A row whose
`published` equals fetch time is a retrieved time, not a publication time;
downstream must not present it as "published at".

## Interests (`interests.json`)

```json
{ "id": "w1", "kind": "keyword|entity|category", "value": "...",
  "region": null, "created_at": 0, "active": true }
```

Soft delete via `active: false` so historical behavior stays reproducible.

## Schedules (`schedules.json`)

Owned by the app layer; the data layer reads. `version` increments on every
edit and is the concurrency gate for suggestions (§5).

```json
{ "id": "s1", "title": "...", "start_at": 0, "end_at": 0,
  "location": "...", "category": "travel|work|health|social|other",
  "notes": "", "version": 1, "updated_at": 0 }
```

## Suggestions (`suggestions.json`)

```json
{ "id": "sg1", "event_id": "s1", "event_version": 1,
  "news_ids": [], "signal_ids": [], "chain": {},
  "status": "pending|accepted|rejected|expired|stale", "created_at": 0 }
```

A `pending` suggestion whose `event_version` no longer matches the schedule
reads as `stale` and must be regenerated, never applied. Rejected suggestions
are not re-surfaced without materially new evidence.

## Evidence mapping (rows → analysis input)

The Agent adapter builds `analysis.md` evidence records from rows:

- `evidence_id`: `sha1(source_id + canonical link)`, 16 hex chars.
- `url`: row `link`.
- `text`: `title` + `summary`, labeled with what was actually available.
- `content_kind`: `summary` unless the row carries verified full text.
- `published_at`: real publication time, or `null` when the row only has a
  fetch time. Unknown dates stay `null`; never invent them.
- `retrieved_at`: always set, RFC 3339.
- Weather rows additionally cite their `day` in text so the model can align a
  forecast with a schedule date.

## Deduplication

1. Same source + canonical link: skip.
2. Cross-source same story: merge, keep earliest time, fullest text, and all
   source names. Repeated coverage is retained as provenance, not treated as
   independent corroboration by default.
3. Same story with changed content: update in place, refresh fetch time.

## Retrieval interface (language-neutral, future)

```text
retrieve(query, since?, categories?, limit=20)
  -> { items: Row[], strategy: "keyword"|"hybrid"|"fallback_recent",
       degraded: bool, candidates_considered: int }
```

Current implementation is keyword/regex over cached rows (`strategy:
"keyword"`). Degradation chain: `hybrid` → `keyword` → `fallback_recent` →
empty. Any step down sets `degraded: true` and the flag travels with the
evidence so the model never mistakes "not retrieved" for "nothing happened".

## Migrations

`meta.json` holds `schema_version`, monotonically increasing. Changes are
additive (new optional fields, new files) unless a version bump documents a
migration. Verify recovery with real filesystem behavior: corrupt cache files
must degrade to empty lists, corrupt user files must keep the last good state
in memory and warn.
