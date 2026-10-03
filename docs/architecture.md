# Architecture

The first slice has two layers:

```text
CLI → TaskRecord → Evidence → JSON receipt
```

The core is deliberately independent of model providers, shell execution, Git, and network
services. Future adapters will sit outside `core.py` and must return explicit evidence rather than
changing task status directly. The task record is the integration seam for worktree execution,
verification, review packets, and resume support.

Review packets are derived views over a verified task record. They bind review context to an exact
revision and repository-relative paths without claiming a merge or deployment.

`forgeyard-provenance-packet/v1` is the deeper aggregate handoff. It embeds the exact UTF-8 bytes
of a task record and each explicit `forgeyard-evidence-receipt/v1`, validates those receipts against
the record and revision, and seals every changed source file with a path, byte count, and SHA-256.
The outer packet has its own canonical digest. `verify-packet` first validates the embedded packet,
then re-reads a caller-supplied source root; it reports `freshness=matched` only when every current
source byte matches. Omitting the source root deliberately yields `freshness=unknown` and `ok=false`.
This makes the packet portable for transport while keeping review admission fail-closed.

The packet never executes commands, resumes work, merges code, or claims deployment. Worktree
creation and future resume adapters remain separate planned boundaries.


## Workbench

The static `docs/workbench` page is a presentation and interaction layer over the same bounded contracts. Its synthetic reports cover MCP Doctor, Agent Proof, and Context Integrity Lab-style handoffs; they are intentionally local, while the CLI and provenance packet remain authoritative for real records.

The checked-in `scripts/run_reference_flow.py` is the executable integration seam for the broader
Agent Systems Lab. It keeps specialist schemas as synthetic inputs, then proves that context,
policy, sandbox, Atlas, proof, resume, and Forgeyard compose through passing, unknown, and digest
tamper outcomes without introducing a second registry or provider dependency.


## Quality receipt

`scripts/benchmark_compose.py` exercises the public CLI through a clean temporary report and record, then emits `forgeyard-benchmark/v1` with iteration count, median, p95 timings, and lower-is-better three-times latency targets. `scripts/benchmark_lab.py` adds a fixed nine-report dataset and measures parse, validation, indexing, replay, composition, and live provenance-packet verification as `forgeyard-lab-benchmark/v1`. The numbers are machine-local performance observations, not adoption or deployment claims. The Workbench publishes the current receipt in `docs/workbench/fixtures/metrics.json`; refresh that fixture only from a fresh benchmark run and keep `result=pass` plus `reviewable=true` as guardrails.
