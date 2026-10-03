# `forgeyard-lab-benchmark/v1`

`scripts/benchmark_lab.py` measures the local Forgeyard path on the checked-in
`forgeyard-workbench-fixture/v1` dataset. The operation set is intentionally
small and explicit:

```text
parse → validate → index → replay → compose → packet_verify
```

Run it from a fresh checkout:

```bash
python scripts/benchmark_lab.py --iterations 20 --warmup 3 --json
```

The receipt records the fixed fixture schema, report count, byte count, dataset
hash, Python/platform identity, sample count, median, p95, minimum, and maximum
for every operation. It also records guards for reviewability, successful live
provenance verification, and the fact that private payloads were not exported.

The dataset and operation order are reproducible. Timing values are deliberately
machine-local observations; they are useful for comparing a fresh run on the
same class of environment, not for ranking machines or claiming provider,
network, database, model, deployment, adoption, or production performance.
