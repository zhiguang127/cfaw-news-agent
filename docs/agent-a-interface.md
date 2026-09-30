# Agent A Runtime Interface

This document is the handoff contract for Agent developer A. It defines the
application-side runtime adapter that assembles an analysis request, calls the
host-managed Octos services, owns request lifecycle, and hands a validated
result to the application. It does not add a second Agent or an app-owned
Octos kernel.

The current executable entry point is still `bundle/main.splash`. The files in
`src/agent/runtime/` are not loaded automatically, so this document describes
the interface to implement and test before one designated integrator moves the
minimum flow into the bundle.

Related contracts:

- Input and result data: `src/contracts/analysis.md`
- Prompt: `src/agent/prompts/news-impact-v1.md`
- Result checks: `src/agent/results/validation-rules.md`
- Suggestion lifecycle: `src/agent/results/change-detection.md`
- Fixed cases: `tests/fixtures/`

## Ownership boundary

Agent A owns:

- request IDs and active-request correlation;
- deterministic input serialization and host-size checks;
- `octos.session.open`, `octos.turn.start`, and `octos.turn.interrupt` calls;
- the adapter state machine, timeout, cancellation, and stale callback handling;
- preserving host `turn_id` as metadata after a successful response;
- passing raw model text to Agent B's parser/validator;
- returning an explicit success or classified failure to `app/`.

Agent A does not own:

- model credentials, provider configuration, or the Octos kernel;
- news ingestion, retrieval, or evidence deduplication;
- deciding whether a claim is factually supported;
- trusting model-generated IDs or correlation metadata;
- writing or changing a schedule;
- presenting a result as accepted before user confirmation.

## Confirmed host protocol

The adapter must use the host-managed services already declared in
`bundle/manifest.json`:

| Service | Parameters | Successful response used by the adapter |
| --- | --- | --- |
| `octos.session.open` | `{}` | `is_ok`; failure exposes `error` |
| `octos.turn.start` | `{ "text": "..." }` | `is_ok`; success data contains `turn_id` and model `text` |
| `octos.turn.interrupt` | `{}` | `is_ok`; failure exposes `error` |

The `text` parameter must be non-empty and no larger than 32768 bytes. The
host returns model text, not the structured analysis result. Agent A must not
assume that the host parses or validates the JSON described in
`analysis.md`.

Do not use `octos.session.history` unless the manifest and target host have
explicitly been updated and the team has agreed on its need. The current app
does not request that permission. Application interests, evidence, schedules,
and decision history come from the app's own context, not host conversation
history.

## Internal request interface

The following is a language-neutral interface. Choose the implementation
language only after verifying how the target runtime loads `src/agent/runtime/`.

```text
AnalysisRuntime.start(snapshot, callbacks) -> RequestHandle
AnalysisRuntime.cancel(request_id) -> void
AnalysisRuntime.state(request_id) -> AdapterState
```

`snapshot` must be one complete input snapshot from `analysis.md`:

```text
{
  schema_version,
  request_id,
  context_version,
  interests,
  evidence,
  schedules,
  previous_decisions
}
```

The runtime may generate `request_id` if the caller has not done so, but it
must never replace a caller-provided ID silently. `context_version` belongs to
the application and is used to reject a result that is no longer current.

`callbacks` should expose these application events:

```text
on_started(request_id)
on_succeeded(ValidatedAnalysisResult)
on_failed(AnalysisFailure)
on_cancelled(request_id)
```

The runtime must emit at most one terminal callback for a request. A callback
from an old request must be ignored after cancellation or supersession.

## Serialization and prompt assembly

1. Validate the input snapshot's required top-level fields and collection IDs
   before contacting Octos.
2. Keep only relevant records, while preserving every record referenced by
   `previous_decisions`.
3. Serialize the snapshot deterministically as JSON. Do not silently truncate
   it to fit the host limit.
4. Add the `news-impact-v1` instructions and the serialized snapshot to the
   turn text. Retrieved article text remains untrusted data inside a clearly
   delimited snapshot; it is not an instruction source.
5. Measure the final UTF-8 byte length, not the character count. If it exceeds
   32768 bytes, reduce context using a documented deterministic policy or fail
   before `turn.start` with an actionable error.

The prompt revision is `news-impact-v1`. Record that revision in the
application-owned analysis metadata after validation; do not ask the model to
provide trusted correlation metadata.

Before `turn.start`, open the application-scoped session. Do not start a second
session or a second Agent for each evidence item.

## State machine

The adapter states are the states defined by the analysis contract:

```text
idle -> running -> succeeded
                 -> failed
                 -> cancelled
```

Rules:

- Only one active analysis request is allowed per application context unless
  the caller explicitly supersedes the previous request.
- `start` while another request is active must either reject with a clear
  busy error or cancel/supersede the old request. It must not allow callbacks
  from both requests to mutate current UI state.
- Only the active request can transition out of `running`.
- A successful host reply is not yet a successful business result. Parse and
  validate it before emitting `on_succeeded`.
- `insufficient_evidence` is a valid business outcome and is not an adapter
  failure. Service errors, timeouts, cancellation, malformed JSON, invalid
  references, unsupported times, and stale context are failures.

## Call sequence

The normal sequence is:

```text
start(snapshot)
  -> create request_id and mark running
  -> serialize and size-check snapshot
  -> host.request("octos.session.open", {}, open_callback)
  -> host.request("octos.turn.start", {text: prompt_and_snapshot}, turn_callback)
  -> parse model text
  -> validate references, outcome, dates, and action
  -> verify request/context is still current
  -> on_succeeded(result with trusted app metadata)
```

If `session.open` fails, do not call `turn.start`. If `turn.start` fails, map
the host error to `service_unavailable` or another actionable runtime failure;
do not return `no_change`. If parsing or validation fails, return the specific
validation category and retain the cause for diagnostics.

## Timeout and cancellation

Use a bounded deadline for each analysis request. The exact duration is a
runtime configuration, not a model instruction. On deadline:

1. atomically mark the request no longer eligible for success;
2. emit or queue a `timeout` failure;
3. call `octos.turn.interrupt` once when a turn is active;
4. wait only for the interrupt acknowledgement within a shorter bounded
   window;
5. ignore any later turn callback;
6. if interruption is not acknowledged, surface that cause and require the
   app to close/reopen or otherwise reset the host session before retrying.

For explicit cancellation, use the same stale-callback guard and classify the
terminal state as `cancelled`. Never let a late successful response overwrite a
newer request or a cancelled state.

## Parsing and validation handoff

Agent A should pass the raw `data.text` plus the original snapshot to Agent B's
deterministic result parser. Agent A must not extract a partial answer with
string matching or accept a code fence as a result.

The parser/validator must enforce the rules in
`src/agent/results/validation-rules.md`, including:

- exactly one JSON object;
- supported outcome and consistent `suggestions` emptiness;
- known interest, evidence, and schedule references;
- evidence citations and content-kind limitations;
- RFC 3339 action times, end after start, and IANA time zone;
- schedule ID/version pairing;
- no executable action when timing is uncertain.

After validation, Agent A attaches application-owned metadata:

```text
request_id
context_version
turn_id
prompt_revision = "news-impact-v1"
validated_at
```

Model-supplied versions, IDs, turn IDs, and prompt revisions are never trusted
as replacements for these values.

## Failure mapping

Category names and meanings are defined only in
`src/contracts/analysis.md` under "Error and outcome categories". The adapter
maps them to terminal states as follows:

| Category | Terminal state |
| --- | --- |
| `service_unavailable` | `failed` |
| `timeout` | `failed` |
| `cancelled` | `cancelled` |
| `invalid_json` | `failed` |
| `invalid_schema` | `failed` |
| `unknown_reference` | `failed` |
| `unsupported_time` | `failed` |
| `stale_context` | `failed` |
| `insufficient_evidence` | `succeeded` |

Every failure should retain an operation, request ID, category, and concise
cause. Do not log API keys, full prompts, article bodies, private schedules, or
credentials.

## Acceptance checklist for Agent A

Before handing the runtime to the integrator, demonstrate with fixed fixtures:

- a valid `no_change` result;
- a valid `insufficient_evidence` result;
- a valid `create` proposal;
- a valid `reschedule` proposal;
- unknown evidence reference rejected as `unknown_reference`;
- stale schedule version rejected as `stale_context`;
- duplicate coverage handled before model-result validation;
- timeout and cancellation ignore late callbacks;
- a second request cannot be overwritten by the first request's response.

The real Octos smoke test must additionally show a model response through Rinx.
That smoke test verifies host connectivity only; it does not replace fixed
validation tests or prove that the complete business flow is integrated.
