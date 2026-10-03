# `forgeyard-workbench-fixture/v1`

The hosted Workbench loads its synthetic specialist reports from
`docs/workbench/fixtures/specialists.json`. The fixture is versioned separately
from the UI so browser behavior can be inspected and changed without hiding
data in JavaScript.

The document contains a `reports` array. Every report has the same bounded
fields used by `forgeyard-compose/v1`: `name`, `schema`, boolean `ok`, a short
`summary`, and non-sensitive `details`. The Workbench adds a failing drift
report in memory for the blocked scenario; it never calls a provider or reads a
real project.

The passing fixture intentionally crosses the public portfolio seam with
`mcp-doctor/v1`, `agent-proof/interop/v1`, `context-integrity/v1`,
`chatlens-trace-envelope/v1`, `atlas-receipt/v1`, `agent-policy/v1`,
`agent-sandbox/v2`, `agent-resume/v1`, and `agent-trace/inspect/v1` reports.
Each report represents a bounded, non-sensitive projection of a real public
owner's contract; raw prompts, transcript text, credentials, and private paths
are not present.

The fixture is presentation data for the synthetic Workbench. The Forgeyard
CLI and provenance packet remain authoritative for real records.

The Workbench also loads `fixtures/adversarial.json` as
`forgeyard-workbench-adversarial/v1`. Each report adds a `threat` classification
to the same bounded fields. The matrix covers stale source, capability denial,
unenforced execution, partial and malformed input, unknown lifecycle, tampered
bytes, path traversal, symlink escape, prompt/secret leakage, schema drift,
duplicate delivery, stale source identity, unbounded output, and false
completion. It is expected to compose into a blocked record, making refusal
behavior inspectable without pretending that every local signal is a successful
outcome.
