# `forgeyard-evaluation/v1`

`scripts/evaluate_lab.py` is the P3 evaluation front door. It combines the
existing deterministic `forgeyard-lab-benchmark/v1` receipt with executed native
contract cases, the static 15-class Workbench catalogue, and optional release
artifact and installation observations.

```bash
python3 scripts/evaluate_lab.py --json
```

The default run reports:

- `correctness`: deterministic benchmark operations and guard checks;
- `refusal`: an executed `forgeyard-runtime-evaluation/v1` receipt and a separate
  `fixture_catalog` describing the static Workbench reports;
- `performance`: machine-local operation measurements;
- `artifact`: wheel, sdist, and `SHA256SUMS` observations when `--dist-dir` is
  supplied, otherwise `unavailable`;
- `install`: a fresh offline wheel consumer when `--dist-dir --install` are
  supplied, otherwise `unavailable`. The consumer runs outside the checkout,
  verifies its import originates in its virtual environment, and must return
  the complete passing native case set with matching package version, corpus,
  suite, and implementation digests.

The v1 `reports`, `unique_threats`, and `mutation_operators` fields are retained
as catalogue metadata. They count stored labels; they are not evidence that an
operation ran. `runtime.cases` records executed outcomes, and
`executed_operators` names the native negative cases. The native suite has its
own [contract](forgeyard-runtime-evaluation-v1.md).

Correctness, catalogue validity, and executed native cases are required. An
omitted distribution directory leaves artifact evidence unavailable and does
not block the default source evaluation. Once `--dist-dir` is supplied, invalid
artifacts block the overall result. Once `--install` is supplied, unavailable,
failed, mismatched, or timed-out consumer evidence also blocks it. The CLI exits
0 for a passing result and 2 for a blocked result.

```bash
python3 scripts/evaluate_lab.py --dist-dir ./dist --install --json
```

Artifact checks reuse the public audit's strict wheel, sdist, and checksum
manifest validator. This checks bytes against the supplied checksum manifest;
it does not authenticate that manifest. Use the release provenance workflow for
authenticated build attribution. Installation processes have explicit timeouts.

The receipt carries the source revision and dataset hashes. It never converts
an unavailable artifact or install observation into a pass, and it never treats
local timing as a cross-machine ranking. The fixtures are synthetic and do not
measure provider, network, database, model, deployment, adoption, or production
behavior.
