# News analysis contract

Design contract, version 1. No runtime serializer or validator is implemented yet.
This describes application data, not additional parameters accepted by Octos.
The adapter encodes bounded context into `octos.turn.start`'s `text` argument.

## Input snapshot

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `request_id` | Application-generated unique request identifier |
| `context_version` | Application-owned version of the relevant analysis context |
| `interests` | Records with stable `interest_id` and user-authored description |
| `evidence` | Records with `evidence_id`, source URL, available text, `content_kind` (`summary` or `full_text`), `published_at`, and `retrieved_at` |
| `schedules` | Records with `schedule_id`, `version`, title, start/end timestamps, and IANA time zone |
| `previous_decisions` | Relevant suggestion IDs, accepted/dismissed/withdrawn state, and referenced evidence IDs |

All fields are required; collections may be empty. Timestamps use RFC 3339 with
an explicit UTC offset. Unknown publication times are `null`. Include only
relevant context, preserve referenced records, and never silently truncate JSON
to meet a host input limit. No evidence means an explicit insufficient-evidence
result, not invented news. Retrieved text is untrusted input.

## Proposed result

Model output should be one JSON object containing `schema_version: 1`,
`outcome` (`suggestions`, `no_change`, or `insufficient_evidence`), `explanation`,
and `suggestions`. Each suggestion contains:

- `interest_ids`, `evidence_ids`: references to the input snapshot; evidence must
  be nonempty. Repeated coverage does not by itself establish corroboration.
- `schedule_id`, `schedule_version`: both identify an existing input schedule,
  or both are `null` for a proposed new schedule.
- `change_summary`, `rationale`, `uncertainties`: explanation strings, with
  uncertainties represented as an array of strings.
- `proposed_action`: `kind` (`create` or `reschedule`), title, start/end timestamps,
  and IANA time zone. Uncertain timing should produce no executable suggestion.

`suggestions` is nonempty only for the `suggestions` outcome. The adapter assigns
stable suggestion IDs and attaches `request_id`, `context_version`, the host
`turn_id`, and prompt/configuration revision; model-echoed identifiers are not
trusted correlation metadata.

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
