# Analysis fixture expectation schema

This document defines the shared `expected` object used by the fixed inputs
under `tests/fixtures/`. It is a test-fixture contract, not a runtime Octos
response schema. The fixtures are synthetic and marked with
`"is_demo_data": true`.

## Shape

Every analysis fixture has these five top-level expectation fields:

```json
{
  "valid": true,
  "usable": true,
  "outcome": "suggestions",
  "error": null,
  "constraints": {}
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `valid` | boolean | The relevant structural assertion passes. For a model fixture, this means the output shape and references satisfy the contract. For a data-only fixture, it means the tested data assertion passes. |
| `usable` | `true`, `false`, or `null` | Whether a valid model result is current and safe to display or apply. `true` means it may proceed; `false` means it must be rejected; `null` means the fixture has no model output and usability is not applicable. |
| `outcome` | enum or `null` | The expected or observed model business outcome defined by the analysis contract. Use `null` for a data-only fixture with no model output, or for an invalid model response whose business outcome must not be trusted. |
| `error` | canonical enum or `null` | The reason a result cannot proceed. Use `null` for a usable business result and for data-only assertions that have no error. Names and meanings come only from `src/contracts/analysis.md`. |
| `constraints` | object | Fixture-specific assertions. Keep these assertions descriptive and deterministic; they must not replace the shared fields. |

## Three-state `usable`

`usable` is intentionally tri-state:

- `true`: a structurally valid and current model result can enter the normal
  display or confirmation flow. Examples: `no_change`,
  `insufficient_evidence`, and valid `suggestions`.
- `false`: the result must not enter that flow. Examples include an unknown
  evidence reference, stale schedule context, or unsupported action timing;
  classify the cause using the canonical table in `analysis.md`.
- `null`: the fixture does not evaluate model-result usability because it has
  no model output. This is not a successful or failed model result.

## Meaning of `outcome: null`

`null` has two deliberately distinct, documented uses:

1. **Data-only fixture:** `analysis-duplicate-coverage.json` has no
   `model_output`. It tests source deduplication, so `usable: null` and
   `outcome: null` mean model-result evaluation is not applicable.
2. **Untrusted model output:** `analysis-invalid-model-output.json` includes a
   model output, but its unknown reference makes the result invalid. Its
   `outcome: null` means no business outcome may be trusted. It therefore has
   `usable: false` and a non-null error from the canonical category set.

By contrast, `analysis-no-change.json` and
`analysis-insufficient-evidence.json` have no `model_output` but still specify
an `outcome`. These fixtures define the expected correct business outcome for
the input scenario, rather than recording an actual model response. They use
`usable: true` because the expected outcome is a valid result if produced.

For a model response rejected because its context is stale, preserve the
response's actual outcome while marking it unusable. For example,
`analysis-stale-schedule.json` uses `outcome: "suggestions"`,
`usable: false`, and the canonical stale-context error category.

## `constraints` and `scope`

`constraints` is always an object, but its properties are fixture-specific.
The optional `scope` property labels which non-standard assertion domain the
fixture covers. It is not required on every fixture and must not be added just
for symmetry.

Currently supported scope labels are:

- `data_deduplication`: the fixture tests evidence/source deduplication rather
  than a model result. This is used by `analysis-duplicate-coverage.json`.
- `model_result`: the fixture tests parsing, validation, outcome, or action
  handling for a model result.
- `lifecycle`: the fixture tests request freshness, cancellation, or decision
  state transitions.

If no scope is needed, omit it. When a new scope is introduced, document it in
this list before using it in a fixture. Existing fixture-specific properties
such as `action_kind`, `requires_user_confirmation`, and
`must_not_apply_schedule_change` remain inside `constraints`.

## Fixture authoring rules

- Keep `expected` keys exactly the five shared fields above.
- Put additional assertions only inside `constraints`.
- Use `outcome: null` only according to the cases documented here.
- Do not use `usable: true` for a data-only fixture.
- Do not treat a valid suggestion as an executed schedule change; constraints
  should state when user confirmation and version checks are required.
- Keep fixture content synthetic and mark it with `is_demo_data: true`.
