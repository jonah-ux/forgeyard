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

The fixture is presentation data for the synthetic Workbench. The Forgeyard
CLI and provenance packet remain authoritative for real records.
