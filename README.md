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

The command prints JSON containing the record path, its SHA-256 digest, and `ready_for_review`.
If any evidence is `fail`, `unknown`, or `skipped`, the record is `blocked` and the command exits
with status 2. A record is not a merge, deployment, or production verification claim.

## Design boundaries

- The core does not call a model provider or execute shell commands.
- Evidence is explicit and tied to an optional source revision.
- Failed evidence blocks review readiness.
- The record is JSON so other agents and CI systems can consume it without scraping prose.
- Later work will add isolated worktrees and bounded command execution behind these contracts.

## Status

This is an early public foundation. Worktree isolation, command capture, resume, review packets,
and cleanup safety are planned vertical slices. They are not represented as implemented here.

## Provenance

This repository is an independent public implementation of general patterns learned while building
automation and agent tooling. It contains no employer source, customer data, credentials, private
paths, production logs, or proprietary operating policy. See `PROVENANCE.md` for the boundary.
