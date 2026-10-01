# Analysis Result Validation Rules

These rules validate model output against the exact input snapshot described
in `src/contracts/analysis.md`. Passing structural validation does not prove
that a claim is factually correct or that cited evidence truly supports it.

## Parse and structure

- Accept exactly one JSON object; reject Markdown fences, trailing prose,
  arrays, and malformed JSON.
- Require `schema_version: 1`, a supported `outcome`, a non-empty string
  `explanation`, and an array `suggestions`.
- `outcome: "suggestions"` requires at least one suggestion. The other outcomes
  require an empty suggestions array.
- Require all fields defined by the result contract. Reject wrong types,
  unknown enum values, and missing required fields rather than silently
  coercing them.
- Require non-empty strings for `change_summary` and `rationale`; require
  `uncertainties` to be an array of strings.

## References and provenance

- Every `interest_id` and `evidence_id` must exist in the input snapshot.
- Every suggestion must cite at least one evidence record.
- Every cited evidence record must have a source URL. Preserve whether its
  content is a `summary` or `full_text`; do not allow the result to upgrade a
  summary into full-text evidence.
- `schedule_id` and `schedule_version` must either both be null or both
  identify the same schedule and version in the input snapshot.
- Ignore model-supplied request IDs, context versions, turn IDs, suggestion
  IDs, and prompt revisions. The application attaches trusted correlation
  metadata after validation.
- Do not count repeated coverage as independent corroboration solely because
  the URLs or source names differ.

## Proposed actions and dates

- During the stage-4 integration, `proposed_action` may be `null`, `create`, or `reschedule`, but never authorizes a write without user confirmation.
  Non-null actions are rejected as `invalid_schema`; they must not be shown as
  pending schedule changes.
- `proposed_action.kind` must be `create` or `reschedule`; its title must be
  non-empty.
- Action start and end must be valid RFC 3339 timestamps with explicit UTC
  offsets; end must be later than start. `timezone` must be a valid IANA time
  zone.
- Reject an executable action when its timing is uncertain or unsupported by
  cited evidence. An uncertain time must be expressed in `uncertainties`, not
  guessed.
- A proposal is not authorization. Before displaying or applying it, the
  application must check that the request is current. Before applying a
  schedule change, require user confirmation, recheck the schedule version,
  and check conflicts.

## Failure classification

Use the canonical category names and meanings defined in
`src/contracts/analysis.md`; this document defines only the checks that select
them. Classify malformed response text, parsed shape or outcome violations,
input-ID mismatches, unsupported action timing, stale request or schedule
versions, host/service failures, deadline expiry, and cancellation according to
that canonical table. Never map an operational or validation failure to
`no_change`. The insufficient-evidence category is a valid business outcome,
not a parser or service failure.
