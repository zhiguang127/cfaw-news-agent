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

## Retrieval interface

```text
retrieve(query, rows, limit)
  -> ranked rows, and records:
     strategy = "keyword" | "fallback_recent"
     degraded = bool
     candidates_considered = int
```

Current implementation, in `bundle/main.splash`:

- The query is split on whitespace; empty terms are dropped.
- Each term is matched case-insensitively (via `regex` + `test`) against the
  row title (weight 3) and summary (weight 1).
- A recency bonus of up to 3 points decays linearly over three days. Rows with
  no timestamp get the full bonus rather than a negative score.
- Ranking is a repeated max scan; the runtime has no array sort.
- An empty query returns the rows unchanged with `strategy: "fallback_recent"`
  and `degraded: true`, so a caller can never mistake an unranked list for a
  ranked one.

**This is keyword scoring, not BM25 and not vector retrieval.** Do not describe
it as hybrid, semantic, or vector-backed. A real BM25 index (FTS5-style) and an
embedding index do not exist yet; the interface is shaped so they can be added
as additional strategies without changing callers.

Degradation chain once those exist: `hybrid` → `keyword` → `fallback_recent` →
empty. Any step down sets `degraded: true`, and the flag travels with the
evidence so the model never mistakes "not retrieved" for "nothing happened".

## Sources

| id | label | kind | needs key |
| --- | --- | --- | --- |
| `hn` | Hacker News | json (Algolia) | no |
| `techmeme` | TechMeme | digest | no |
| `google` | Google News (en-US) | rss | no |
| `airchina` | 国航 | rss | no |
| `hefeng` | 和风逐小时 | hefeng | **yes** |
| `hefeng_warn` | 天气预警 | hefeng | **yes** |

### City forecasts are not sources

Weather is not in `sources`. `city_list` holds 30 major mainland China cities
as `{cid, name, lat, lon}`; `cid` is `w01`…`w30` because map keys must be
ASCII identifiers.

- `tracked` is the list of cities actually fetched, starting at 5.
- `pick_city(name)` adds the city and fires one request the first time it is
  picked, so the app never pays for forecasts nobody looks at.
- `fetch_cities` runs them **in parallel** and does not touch `busy`: one slow
  city must not stall the news chain, and 30 cities must not cost 30 serial
  round trips. `weather_pending` drives the status line.
- `weather_city_rows()` merges tracked cities grouped by city then day, filtered
  by `city_sel` (`全部` means every tracked city).
- `today_rows()` skips weather so forecasts never flood the interleaved feed.

Adding a city means adding a `cid` key to both `rows_by` and `failed_by` as
well as the `city_list` entry.

Frontend: the natural end state is a picker driven by schedule locations
(`schedules[].location`), so forecast cities follow the user's trips instead of
a fixed list. That is a contract change and needs agreement, not a local edit.

## Runtime constraints that shaped this

The splash runtime's real method surface is small. Verified from
`makepad/platform/script/src/string.rs` and `array.rs`:

- string: `len` `trim` `replace` `split` `index` `search` `match_str`
  `captures` `match_all` `parse_json` `to_chars` `to_f64` `strip_prefix`
  `strip_suffix` `url_encode` `url_decode`
- array: `len` `push` `pop` `remove` `retain` `clear` `to_string` `parse_json`
- globals used here: `regex` `time_now` `floor` `fs` `start_timeout`

There is **no** `lower`, `contains`, `sort`, `range`, or `get` method.
`lower`/`upper`/`len` exist only as `text.*` standard-library functions, not as
string methods. Use `regex` for matching and index loops for ordering.

Two further runtime rules found the hard way:

1. Reading a field a record does not declare is a **runtime error**, not `nil`.
   Every record must declare the same field set.
2. The same holds for maps: a key absent from `rows_by` / `failed_by` reads as
   `nil`, and `nil` has no `len()`. Adding a source or city means adding its id
   to both maps, or the feed dies on the first fetch. Map keys must also be
   ASCII identifiers: `w01`, not `w北京`.
3. A widget declared `visible: false` does not reliably come back with
   `set_visible`. Render conditional UI inside an `on_render` that already
   runs, rather than toggling a hidden declaration.
3. `octoscript check` is stricter than the splash runtime and reports false
   positives for Makepad extensions (`#x` colors, `+:`, two-variable `for`).
   It also rejects `.len()` on strings, which the runtime accepts. Use it for
   syntax only, and confirm behavior with `card-host`.

## Migrations

`meta.json` holds `schema_version`, monotonically increasing. Changes are
additive (new optional fields, new files) unless a version bump documents a
migration. Verify recovery with real filesystem behavior: corrupt cache files
must degrade to empty lists, corrupt user files must keep the last good state
in memory and warn.
