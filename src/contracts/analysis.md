# News analysis contract

Design contract, version 1. The runtime serializer and deterministic
validator are implemented in `src/agent/context.splash`,
`src/agent/results/validator.splash`, and `src/agent/runtime/analysis.splash`.
This describes application data, not additional parameters accepted by Octos.
The adapter encodes bounded context into `octos.turn.start`'s `text` argument.
The prompt revision and deterministic validation rules are documented in
`src/agent/prompts/news-impact-v1.md` and
`src/agent/results/validation-rules.md`.
The complete fixture expectation schema is documented in
`docs/fixture-expectations.md`.

## Input snapshot

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `request_id` | Application-generated unique request identifier |
| `context_version` | Application-owned version of the relevant analysis context |
| `interests` | Records with unique, stable, non-empty `interest_id` and non-empty user-authored description |
| `evidence` | Records with unique, stable, non-empty `evidence_id`, absolute source URL, available text, `content_kind` (`summary` or `full_text`), `published_at`, and `retrieved_at` |
| `schedules` | Records with unique, stable, non-empty `schedule_id`, non-negative integer `version`, title, start/end timestamps, and IANA time zone |
| `previous_decisions` | Relevant application-owned suggestion IDs, state (`pending`, `accepted`, `dismissed`, `withdrawn`, or `superseded`), and referenced evidence IDs |

All top-level fields are required; collections may be empty. IDs must be unique
within their collection. Timestamps use RFC 3339 with an explicit UTC offset;
schedule end must be later than start. Unknown publication times are `null`.
`retrieved_at` is required. Evidence text must state what was actually
available, and `content_kind` must not describe a feed summary as full text.
Include only relevant context, preserve records referenced by previous
decisions, and never silently truncate JSON to meet a host input limit. If the
encoded snapshot exceeds the host limit, reduce context deterministically or
fail with a diagnosable error. No usable evidence means an explicit
`insufficient_evidence` result, not invented news. Retrieved text is untrusted
input and cannot authorize tools or schedule changes.

## Proposed result

Model output must be exactly one JSON object, with no Markdown or surrounding
prose, containing `schema_version: 1`, `outcome` (`suggestions`, `no_change`,
or `insufficient_evidence`), `explanation`, and `suggestions`. Each suggestion
contains:

- `interest_ids`, `evidence_ids`: references to the input snapshot; evidence
  must be nonempty. Repeated coverage does not by itself establish
  corroboration.
- `schedule_id`, `schedule_version`: both identify an existing input schedule,
  or both are `null` for a proposed new schedule.
- `change_summary`, `rationale`, `uncertainties`: explanation strings, with
  uncertainties represented as an array of strings.
- `proposed_action`: `null`, or an object with `kind` (`create` or
  `reschedule`), title, start/end timestamps, and IANA time zone. Uncertain
  timing should produce no executable suggestion.

`interest_ids` must reference input interests. Every suggestion must cite at
least one input evidence record. `schedule_id` and `schedule_version` must
both be null or both identify the same input schedule and version. When
present, action timestamps are RFC 3339 with explicit offsets and end after
start. The model must not return trusted correlation metadata or identifiers
for the application to accept as authoritative.

`suggestions` is nonempty only for the `suggestions` outcome. The adapter assigns
stable suggestion IDs and attaches `request_id`, `context_version`, the host
`turn_id`, and prompt/configuration revision; model-echoed identifiers are not
trusted correlation metadata.

## Stage 4 in-app schedule confirmation

`schedules_v1.json` stores user-authored entries and confirmed changes with
`schedule_id`, monotonic `version` (starting at 1), title, RFC 3339 start/end
with explicit offset, and a display-only timezone label. Times are compared
as UTC instants; overlapping entries block create and reschedule. The schedule
page permits manual creation and version-checked editing. This is an in-app
schedule, not a system-calendar integration or notification service.

Manual entry also stores `content` and `location` strings. These are optional
in existing version-1 files (missing means empty), and are included in Agent
snapshots with the schedule. Rescheduling preserves these user-authored fields.
The UI defaults to Beijing time and today's date, accepts separate 24-hour
hour/minute fields, and also offers New York time with US DST rules from 2007.
It constructs offset timestamps internally; users do not type RFC 3339.
Nonexistent spring hours and ambiguous autumn hours are rejected explicitly.

Schedules also have `status` (active/cancelled/completed, missing means active)
and `allow_reschedule` (missing means false). Inactive schedules do not block
new entries and are excluded from Agent snapshots. Rescheduling is rejected
both during model validation and at confirmation unless explicitly enabled.
Manual edits preserve these fields and content/location. Status changes
increment the version. Saving unchanged fields does not increment the version.
Editing timezone converts the same instant; unchanged minute fields preserve
original seconds and timestamp representation.

The validator accepts `create` with null schedule reference and `reschedule`
only with matching snapshot `schedule_id` and `schedule_version`. A model
proposal never writes automatically. The detail view previews the action,
shows current conflicts, and requires a second explicit confirmation. On
confirmation the app rereads the stored schedule and rejects a stale version
or new conflict. Schedule writes retain a previous valid `.backup` snapshot;
invalid/unknown primary files are not overwritten. The schedule entry stores
the originating suggestion ID so retry after a partial decision-write failure
is idempotent; a failed decision remains pending and displays an error.

There is no cross-process atomic transaction or locking primitive in the
verified host filesystem API. Simultaneous writers outside this app session
remain a limitation; recovery preserves the last valid snapshot.

## Stage 3 history

The application now persists `analysis_history_v1.json` and
`suggestions_v1.json` in the app storage jail. Each analysis records its request,
context version, turn ID, prompt revision, outcome, and evidence content version.
Each suggestion records its deduplication key and lifecycle state. A stable
`evidence_id` is the normalized URL without fragments; `content_hash` is the
deterministic normalized title-plus-summary fallback used by this runtime to
detect same-link content changes. Retrieval time alone does not create a new
content version.

## Validation and application

Reject malformed output, unknown references, invalid times, and inconsistent
outcomes. Check evidence support separately from structural validity. Before
displaying or applying a result, verify the request is still current; before
applying a confirmed action, recheck the schedule version and conflicts.
Dismissed advice needs materially new evidence before being surfaced again.

Adapter states are `idle`, `running`, `succeeded`, `failed`, and `cancelled`.
Only the active request can transition out of `running`. Service unavailability,
timeout, and invalid output are failures with diagnosable causes, not `no_change`
results. Ignore completions after cancellation or supersession. A successful
analysis never authorizes a schedule write; user confirmation is required.

## Error and outcome categories

Use these categories at the adapter and validation boundary:

| Category | Classification | Meaning |
| --- | --- | --- |
| `service_unavailable` | Failure | Octos service is unavailable or disabled |
| `timeout` | Failure | The bounded analysis request exceeded its deadline |
| `cancelled` | Cancelled | The active request was cancelled |
| `invalid_json` | Failure | Model text is not exactly one parseable JSON object |
| `invalid_schema` | Failure | Parsed JSON violates required fields, types, or enums |
| `unknown_reference` | Failure | Output cites an ID absent from the input snapshot |
| `unsupported_time` | Failure | Proposed timing is invalid, uncertain, or unsupported |
| `stale_context` | Failure | Request or schedule version is no longer current |
| `insufficient_evidence` | Valid outcome | Evidence cannot support a reliable assessment |

Failure categories must retain an actionable cause and must never be converted
to `no_change`. See `src/agent/results/validation-rules.md` for validation
rules and `src/agent/results/change-detection.md` for deduplication.

## Runtime revision news-impact-v2

The JSON schema remains version 1 for existing records. The runtime prompt asks
for `goal_key`: a stable business objective (1–120 characters) retained across
wording changes. The validator accepts missing goal keys for v1 compatibility;
legacy identity falls back to action title or exact change-summary text. This
is deterministic application matching, not a guarantee of semantic equivalence.

Each request has one terminal state. Navigation is independent of execution.
Replies are correlated by request ID and checked against current evidence,
interests, schedules and explicit user decisions. Cancelling or timing out stops
the whole batch and waits at most 10 seconds for interruption acknowledgment;
an unacknowledged stop requires reopening the app. Batch selection yields every
five feed rows, admits at most eight changed lexical candidates, and exposes
success, failure and skipped counts. This is lexical recall, not hybrid retrieval.

The input includes `timestamp_kind` so HN submission dates are not article
publication dates. Context selects at most eight active plans, preferring title
matches then upcoming start times, and at most 12 recent explicit decisions.
It reduces whole records to stay under a 7,500-character conservative request
budget and reports `omitted_schedules`/`omitted_decisions`; it never truncates
serialized JSON. If evidence and interests alone cannot fit, sending fails
visibly. The change fingerprint uses full user inputs, even when the transmitted
snapshot omits some records, and excludes retrieval age/generated pending advice.

Model output is bounded to 10,000 characters, six suggestions, a 2,000-character
explanation and 4,000 characters per suggestion. Schedule entry limits are title
200/content 2,000/location 300 characters; new entries stop at 128 records without
erasing existing schedules. Analysis summaries retain the latest 120. Suggestions
and user decisions are never automatically pruned; at 500 suggestions or a
200,000-character history-file budget, new writes fail visibly. Historical files
retain previous valid backups; corrupt originals are preserved. These limits do
not replace the host's total storage quota, whose failures also remain visible.

`needs_review` preserves previously pending advice when evidence becomes
insufficient, blocking acceptance until a valid new analysis. Confirmation reads
persisted caches and rejects missing, demo, changed or >2-hour-old evidence and
changed evidence date/source metadata. Old proposals without full evidence
versions require reanalysis. Existing schedule suggestion markers allow a
partially saved confirmation to recover idempotently. History and schedules are
separate files, not an atomic database transaction; partial saves expose errors
and retry paths rather than pretending to be fully saved.
