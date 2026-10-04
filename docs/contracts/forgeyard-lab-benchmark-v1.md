# `forgeyard-lab-benchmark/v1`

`scripts/benchmark_lab.py` measures the local Forgeyard path on the checked-in
`forgeyard-workbench-fixture/v1` dataset. The operation set is intentionally
small and explicit:

```text
parse → validate → index → replay → compose → packet_verify
```

Run it from a fresh checkout:

```bash
python3 scripts/benchmark_lab.py --iterations 20 --warmup 3 --json
```

The receipt records the fixed fixture schema, report count, byte count, dataset
hash, Python/platform identity, sample count, median, p95, minimum, and maximum
for every operation. It also records guards for reviewability, successful live
provenance verification, and the fact that private payloads were not exported.

Each operation also runs once under `tracemalloc`, outside the latency samples,
and records `memory.state=measured`, `samples=1`, and `peak_python_bytes`.
This is the peak traced Python allocation during that operation. It is not RSS,
native allocations, total process memory, or a repeated memory distribution.
If the caller already owns a tracing session, memory stays `unavailable` with
`reason=caller_tracing_active`; the benchmark preserves that caller's state.

`measurement_protocol` identifies the latency timer, separate memory method,
operation order, and whether caller tracing was active during latency sampling.
Tracing can affect latency, so runs with different tracing states are not
comparable. `runtime` records Python/platform, architecture, and the
reported logical CPU count (or null when unavailable), without a hostname.

For comparisons, save each JSON receipt. Treat its `schema`, `dataset.sha256`,
`measurement_protocol`, `runtime`, `iterations`, and `warmup` as the baseline
manifest. Compare operation metrics only when those fields match and both
receipts pass their guards. Keep baseline and candidate median/p95 and min/max
in separate columns; report the absolute and relative difference as a local
observation. Mismatched inputs or protocols are incomparable, and unavailable
memory is not zero. The dated Workbench metrics fixture remains its historical
compose/verify snapshot and does not gain new measurements from this change.

The dataset and operation order are reproducible. Timing values are deliberately
machine-local observations; they are useful for comparing a fresh run on the
same class of environment, not for ranking machines or claiming provider,
network, database, model, deployment, adoption, or production performance.
