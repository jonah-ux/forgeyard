# Forgeyard

**Reviewable, reproducible delivery records for coding-agent work.**

Forgeyard is a small local-first foundation for running software tasks in isolation, recording what
was tested, and refusing to call a task complete when its evidence contains a failure or an
unknown result.

The first vertical slice is intentionally narrow: it defines a durable task record and a
machine-readable evidence contract before adding worktree execution, provider adapters, or a web
interface. That order keeps the truth model testable.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
forgeyard create \
  --task-id demo-001 \
  --repository fixture-repo \
  --request "add a feature" \
  --evidence tests=pass:3\ passed \
  --evidence diff=pass:clean\ diff \
  --output ./artifacts/demo-001.json
```

For a zero-setup walkthrough that creates, verifies, and packets a synthetic record:

```bash
forgeyard demo
```

The command emits one `forgeyard-demo/v1` JSON document and uses a temporary directory, so it
leaves no project files behind.

Compose bounded reports from specialist tools such as MCP Doctor or Agent Proof without copying their raw payloads into the task record:

```bash
forgeyard compose \
  --task-id mcp-check-001 \
  --repository fixture-repo \
  --request "review MCP contract" \
  --input contract=./artifacts/mcp-doctor.json \
  --input proof=./artifacts/agent-proof.json \
  --output ./artifacts/review-record.json
```

Each input must be a JSON object with a boolean `ok` field. Forgeyard stores only the input name,
its schema label, the boolean result, and the optional revision; the specialist payload remains in
its own file. A false result blocks the record, and malformed or missing `ok` values are rejected.

The public compose contract is documented in [`docs/contracts/forgeyard-compose-v1.md`](docs/contracts/forgeyard-compose-v1.md). Run the bounded CLI quality receipt with `python scripts/benchmark_compose.py --json`; it measures the same compose and verify path used by the Workbench story.

The command prints JSON containing the record path, its SHA-256 digest, and `ready_for_review`.
If any evidence is `fail`, `unknown`, or `skipped`, the record is `blocked` and the command exits
with status 2. A record is not a merge, deployment, or production verification claim.

Verify a saved record before handing it to a reviewer:

```bash
forgeyard verify ./artifacts/demo-001.json --sha256 <sha256-from-create>
```

The optional digest pin makes the verifier prove that the bytes you reviewed are the bytes that were created. The verifier rejects malformed JSON and contradictory status/evidence combinations. It reports a
`forgeyard-record-verify/v1` document and never upgrades a blocked record to reviewable.

Build a reviewer handoff only from a verified, passing record:

```bash
forgeyard review ./artifacts/demo-001.json \
  --sha256 <sha256-from-create> \
  --revision abc123 \
  --path src/change.py \
  --path tests/test_change.py
```

The result is a `forgeyard-review-packet/v1` document containing the request, exact revision,
repository-relative changed paths, evidence, artifact references, and the verified record digest.
Passing `--sha256` binds packet creation to the exact bytes produced by `create`; a tampered or
substituted record is rejected before the packet is emitted. Unknown, skipped, or failed evidence
cannot produce a packet. Evidence names must be non-empty and unique, and evidence revisions, when
present, must match the packet revision. Paths
must be non-empty, slash-separated repository paths without `.` or `..` segments.

For a multi-source handoff, create explicit evidence receipts and seal them with a portable
provenance packet:

```bash
forgeyard receipt ./artifacts/demo-001.json \
  --name tests --path tests/test_change.py \
  --output ./artifacts/tests.receipt.json
forgeyard receipt ./artifacts/demo-001.json \
  --name diff --path src/change.py \
  --output ./artifacts/diff.receipt.json
forgeyard packet ./artifacts/demo-001.json \
  --receipt ./artifacts/tests.receipt.json \
  --receipt ./artifacts/diff.receipt.json \
  --source-root . --revision abc123 \
  --path src/change.py --path tests/test_change.py \
  --output ./artifacts/review.provenance.json
forgeyard verify-packet ./artifacts/review.provenance.json --source-root .
```

`forgeyard-provenance-packet/v1` embeds the exact record and receipt bytes, binds every receipt to
the task record and revision, and stores SHA-256 seals for each changed source file. Verification
is fail-closed: a missing or changed source, malformed receipt, receipt mismatch, or unknown live
source root cannot produce an `ok` result. The packet remains portable for transport and inspection,
but a reviewer must provide the live `--source-root` to turn its embedded seals into a fresh result.
The packet contains task and evidence details supplied by the caller; do not put secrets in records.

## Design boundaries

- The core does not call a model provider or execute shell commands.
- Evidence is explicit and tied to an optional source revision.
- Failed evidence blocks review readiness.
- The record is JSON so other agents and CI systems can consume it without scraping prose.
- Evidence receipts are explicit, source-bound, and revision-bound; a provenance packet cannot
  silently substitute a different receipt or source tree.
- Later work will add isolated worktrees and bounded command execution behind these contracts.

The second slice now admits a worktree plan without mutating anything:

```bash
forgeyard plan-worktree --source ./fixture-repo --destination /tmp/forgeyard-task --revision HEAD
```

The planner canonicalizes paths, refuses a destination inside the source checkout, refuses an
existing destination, and emits an argument list rather than a shell string. Actual creation is a
separate bounded operation:

```bash
forgeyard create-worktree --source ./fixture-repo --destination /tmp/forgeyard-task --revision HEAD
```

Creation uses `git worktree add --detach` with an argument list and a bounded timeout. It does not
run an agent, alter the source checkout, or claim that the resulting task is tested or reviewed.

## Status

This is an early public foundation. Worktree isolation, command capture, resume, and cleanup safety
remain planned vertical slices. Review packets and the provenance packet are local review inputs;
they are not merge, deployment, or runtime verification claims.

## Provenance

This repository is an independent public implementation of general patterns learned while building
automation and agent tooling. It contains no employer source, customer data, credentials, private
paths, production logs, or proprietary operating policy. See `PROVENANCE.md` for the boundary.

## Interactive flagship

Open the [Forgeyard Workbench](https://jonah-ux.github.io/forgeyard/) to run the
synthetic review flow in a browser. It has four inspectable paths:

- **Passing case:** MCP Doctor and Agent Proof-style reports compose into `READY` evidence.
- **Failing case:** an `MCP010` drift report composes into `BLOCKED` evidence.
- **Tamper case:** changing the sealed request produces `REFUSED` integrity state.
- **Export case:** the composed JSON record downloads as a portable artifact.

The page is static and local-first; it contains no credentials, network calls,
customer data, or hidden provider state.
