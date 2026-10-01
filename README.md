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

## Design boundaries

- The core does not call a model provider or execute shell commands.
- Evidence is explicit and tied to an optional source revision.
- Failed evidence blocks review readiness.
- The record is JSON so other agents and CI systems can consume it without scraping prose.
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

This is an early public foundation. Worktree isolation, command capture, resume, review packets,
and cleanup safety are planned vertical slices. They are not represented as implemented here.

## Provenance

This repository is an independent public implementation of general patterns learned while building
automation and agent tooling. It contains no employer source, customer data, credentials, private
paths, production logs, or proprietary operating policy. See `PROVENANCE.md` for the boundary.
