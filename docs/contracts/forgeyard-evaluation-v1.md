# `forgeyard-evaluation/v1`

`scripts/evaluate_lab.py` is the P3 evaluation front door. It combines the
existing deterministic `forgeyard-lab-benchmark/v1` receipt with the public
15-class adversarial Workbench fixture and optional release-artifact/install
observations.

```bash
python scripts/evaluate_lab.py --json
```

The default run reports:

- `correctness`: deterministic benchmark operations and guard checks;
- `refusal`: adversarial report count, unique threat count, mutation-operator
  names, and fixture SHA-256;
- `performance`: machine-local operation measurements;
- `artifact`: wheel, sdist, and `SHA256SUMS` observations when `--dist-dir` is
  supplied, otherwise `unavailable`;
- `install`: an offline wheel consumer check when `--dist-dir --install` are
  supplied, otherwise `unavailable`.

The receipt carries the source revision and dataset hashes. It never converts
an unavailable artifact or install observation into a pass, and it never treats
local timing as a cross-machine ranking. The fixtures are synthetic and do not
measure provider, network, database, model, deployment, adoption, or production
behavior.
