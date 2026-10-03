# `forgeyard-reference-flow/v1`

The reference flow is a checked-in, offline integration exercise for the Agent Systems Lab. It
connects bounded synthetic reports through the same Forgeyard CLI that a reviewer can install from
the repository:

```text
context admission → capability policy → sandbox receipt → Atlas lifecycle
                 → proof envelope → resume checkpoint → Forgeyard compose/verify
```

Run the three expected outcomes from a fresh checkout:

```bash
python scripts/run_reference_flow.py --scenario passing
python scripts/run_reference_flow.py --scenario blocked
python scripts/run_reference_flow.py --scenario tampered
```

Every command prints `forgeyard-reference-flow/v1` JSON and returns zero when the expected behavior
is observed. `passing` produces a reviewable record. `blocked` injects an `ai-work-evidence/v1`
unknown status at the Atlas boundary and expects Forgeyard to preserve the blocked decision.
`tampered` first composes a passing record, changes its request bytes, and expects digest-pinned
verification to refuse the record.

The reports are synthetic owner-shaped projections. They contain no raw prompts, transcript text,
customer data, credentials, private paths, provider calls, or production state. The flow proves
that the boundaries compose and refuse as designed; it does not claim that any external repository
has adopted this script or that a production workflow is deployed.

The script is intentionally a reference harness rather than a second protocol registry. Each
specialist schema remains owned by its source repository, while Forgeyard owns the final bounded
review record and digest verification.
