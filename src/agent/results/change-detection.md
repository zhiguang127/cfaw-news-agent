# Suggestion change detection (runtime revision v2)

Compare each news item with its **latest** saved analysis input: evidence text,
URL and timestamp semantics, complete interests/schedules, and explicit user
decisions. A→B→A is a change. Retrieval age, refresh generations, page navigation,
and generated pending suggestions do not themselves change this fingerprint.
An unsaved session result remains eligible for analysis/recovery.

Business identity is structured JSON of canonical unique interest/evidence IDs,
schedule ID, stable goal and action kind. Exact proposal identity also includes
schedule version and UTC start/end. Identifier order and wording changes with
the same goal do not create another objective. Different goals on the same news
remain independent. `goal_key` is requested by the prompt and validated for type
and length, not trusted as an application suggestion ID. Legacy proposals use
exact change-summary/action-title fallback; this cannot prove semantic identity.

Within one business identity, identical pending advice is reused. A changed
pending proposal is superseded. Accepted/dismissed/withdrawn decisions with the
same evidence version suppress repeated advice; changed supporting evidence can
produce a new pending record. Prior accepted schedule changes are never undone.

`no_change` withdraws pending/needs-review records only for schedule coverage in
the actual snapshot (schedule-free advice is covered). Uncovered plans remain
`needs_review`. `insufficient_evidence` preserves pending advice as `needs_review`
and blocks acceptance. All explicit decisions remain stored.

Every confirmed action still checks persisted evidence freshness/content/date
semantics, live interest membership, schedule version and conflicts. A cached
article snapshot is useful for explanation, but never substitutes for currently
verifiable evidence. See `src/contracts/analysis.md` for limits and recovery.
