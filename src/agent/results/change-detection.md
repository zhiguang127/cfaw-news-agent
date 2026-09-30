# Suggestion Change Detection

Change detection is deterministic application logic, not a model-generated
identity decision. Compare validated proposals with prior decisions before
showing them to the user.

## Decision states

Persist these application-owned states for each suggestion:

- `pending`: awaiting the user's decision
- `accepted`: the user accepted it
- `dismissed`: the user rejected it
- `withdrawn`: the application no longer considers it supported
- `superseded`: a materially updated proposal replaced it

Only explicit user confirmation may apply a proposed schedule change.

## Stable deduplication key

Build a canonical key from validated, sorted identifiers and action fields:

```text
interest_ids + evidence_ids + schedule_id (or null)
+ schedule_version (or null) + proposed_action.kind (or null)
```

Use the canonical representation as a lookup key or hash it in the application.
Do not accept a model-generated suggestion ID or deduplication key. Keep the
original evidence references and decision history alongside the key.

## Suppression and reconsideration

Do not create another visible suggestion when the same deduplication key has
already been analyzed and there is no material change. A model wording change,
request ID change, or retrieval timestamp change alone is not material new
evidence.

For a dismissed suggestion, suppress it unless at least one of these is true:

- A genuinely new evidence record changes the supported facts or their
  significance; duplicate coverage alone does not qualify.
- The previous proposal was withdrawn and new evidence now supports a
  materially different conclusion or action.
- The relevant schedule version changed; do not reuse the old proposal. Mark
  the old one stale and analyze against the current schedule snapshot.

When material evidence changes an existing pending proposal, mark the prior
proposal `superseded` and create a new application-owned suggestion record.
When evidence no longer supports a pending proposal, mark it `withdrawn`.
Accepted decisions remain in history; a later material development may produce
a new proposal but must not silently undo the accepted schedule change.

## Stale context and safety

Before showing a result, verify its request and context versions are still
current. Before applying a confirmed schedule action, verify the schedule still
has the version referenced by the proposal and recheck conflicts. On mismatch,
return `stale_context` and request fresh analysis; never silently retarget the
proposal to a newer schedule version.

The application must retain enough evidence IDs and decision history to
explain why advice was repeated, revised, withdrawn, or suppressed.
