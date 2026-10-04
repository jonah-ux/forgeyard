# `forgeyard-runtime-evaluation/v1`

```console
forgeyard evaluate-refusals
```

This package-owned command executes synthetic operations against the installed
Forgeyard implementation. It needs no other package, provider, credential, or
service. Each case has an isolated temporary directory that is removed after
execution.

The 19-case corpus starts with a passing record, projection, and source-bound
provenance control. Negative cases exercise duplicate evidence, schema drift,
unbounded summaries, raw-field injection, malformed roots and reports, unknown
projections, nonpassing evidence, false completion, payload redaction, revision
mismatch, path traversal, record and packet tampering, stale or unbound sources,
symlink escape, and duplicate receipts.

Each `cases` entry records `name`, `boundary`, `expected`, `observed`, `executed`,
`ok`, and `error_type`. Refusal exceptions must match the expected owning-layer
reason. An unrelated refusal, unexpected exception, missing admission, or
accepted negative input fails the case. Unexpected exception messages and
temporary paths are excluded from the receipt. A failed case blocks the whole
suite; the CLI exits 0 for pass and 2 for blocked.

`corpus_sha256` hashes canonical case specifications. `suite_sha256` hashes the
executing suite's source file. `implementation_sha256` hashes the native core
and interop source files. `package_version` and `python` identify the executing
runtime. These are reproducibility metadata, not independent authentication or
a substitute for release attestations.

The v1 specification digest is
`5f70a79f2be8dc48ec26ec4f569951e342ea7717997b11084104cbfc63e0733e`.
The producer and lab consumer require the complete 19-case corpus with this
digest. An empty, shortened, reordered, duplicated, or changed corpus cannot
pass by reporting a success label; changing the public corpus requires an
explicit contract revision.

Regression tests deliberately replace the packet verifier with one that accepts
everything: the passing control still passes while stale, tampered, and unbound
cases fail. Tests also inject unexpected exceptions and check that their message
content is excluded. This demonstrates that the suite detects those changes;
it does not establish complete mutation coverage.

The report projection case checks both `ok=true` to PASS and `ok=false` to FAIL,
including the bounded schema detail, evidence name, revision, and payload
redaction. Suppressing a passing result or upgrading a failed report fails the
case even when raw payload content remains absent.

The scope is native Forgeyard contracts on synthetic local inputs. Workbench
threat labels remain a separate static catalogue. The suite does not execute
specialist policy, sandbox enforcement, network, provider, deployment, adoption,
or production behavior. Timing observations belong to the lab benchmark and
remain specific to the machine where they were measured.
