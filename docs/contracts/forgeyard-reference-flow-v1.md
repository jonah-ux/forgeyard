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
python3 scripts/run_reference_flow.py --scenario passing
python3 scripts/run_reference_flow.py --scenario blocked
python3 scripts/run_reference_flow.py --scenario tampered
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

## Opt-in installed mode

The same script has an opt-in `--mode installed` path for a real local package handoff. It consumes
an owner-produced ChatLens trace and Atlas state file, invokes the installed `chatlens`, `atlas`,
`agent-proof`, and `forgeyard` commands through an explicit command map, and records only versions,
exit codes, and stdout/stderr digests:

```bash
python3 scripts/run_reference_flow.py \
  --mode installed --scenario passing \
  --chatlens-trace ./artifacts/chatlens.trace.jsonl \
  --atlas-state ./artifacts/atlas-events.jsonl
```

The installed path runs `trace-import` and `evidence-export`, `atlas evidence`, Agent Proof
`normalize`/`verify-interop`, and Forgeyard `compose`/`verify`. `blocked` changes only the synthetic
Atlas evidence status to `unknown` after the owner command so the refusal path remains deliberate;
`tampered` changes the composed record bytes after its digest is captured. Missing commands or
owner artifacts produce `outcome=unavailable`; no fixture fallback is substituted.

The installed receipt is `forgeyard-installed-reference-flow/v1`. It proves a local handoff against
the supplied files and installed versions. It does not claim that the packages share a release
lock, that an external user adopted them, or that any production workflow was deployed.

The four-package release lock is recorded separately in
[`forgeyard-installed-flow-release-lock/v1`](forgeyard-installed-flow-release-lock-v1.md). It
pins published artifact hashes and tagged commits while keeping the editable public-main consumer
observation clearly labeled.
