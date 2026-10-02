# `forgeyard-compose/v1`

`forgeyard compose` turns bounded JSON reports from specialist tools into one
Forgeyard task record. The contract is intentionally loss-aware: it carries the
report name, schema label, boolean result, and optional revision, while leaving
the raw specialist payload in its original artifact file.

## Input

Each `--input` argument has the form `NAME=REPORT.json`. The report must be a
UTF-8 JSON object containing:

```json
{
  "schema": "mcp-doctor/v1",
  "ok": true
}
```

`schema` is optional and becomes `unknown` when absent. `ok` is required and
must be a JSON boolean. A missing, malformed, or non-boolean result is rejected.
The reviewed `agent-proof/interop/v1` envelope is also accepted when its
`projection.status.ok` field is a JSON boolean. Callers should run Agent Proof's
source-bound `verify-interop --require-input` gate before composing that envelope.

## Output

A successful command prints a `forgeyard-compose/v1` envelope:

```json
{
  "schema": "forgeyard-compose/v1",
  "record": "artifacts/review-record.json",
  "sha256": "…",
  "status": "ready_for_review"
}
```

The written record contains one evidence item per input. A `false` result makes
the record `blocked`; every input must be `true` for `ready_for_review`. The
record detail contains only `schema=<label>; ok=<true|false>`.

## Boundary

The contract proves that supplied specialist results were bounded into a
review record. It does not prove that a provider, deployment, user-visible
outcome, or original command execution happened. The caller remains responsible
for retaining and independently verifying the raw reports and any provenance
packet built from the record.
