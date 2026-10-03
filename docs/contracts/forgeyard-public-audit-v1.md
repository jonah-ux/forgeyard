# `forgeyard-public-audit/v1`

`scripts/audit_public_surface.py` is the first P4 hardening receipt. It audits
the public Forgeyard checkout without contacting providers or reading private
state:

```bash
python scripts/audit_public_surface.py --json
```

The receipt contains:

- a dependency inventory from `pyproject.toml`;
- a declared-license and `LICENSE` check;
- release-workflow provenance markers and required security/provenance docs;
- a high-signal secret/private-key scan over tracked text files;
- optional wheel/sdist/`SHA256SUMS` verification when `--dist-dir` is supplied.

The scan reports relative public file names and finding classes, never matched
secret bytes. It is a high-signal guard, not a complete DLP or security proof.
Artifact verification is explicitly `unavailable` without a supplied dist
directory. A passing audit does not claim security, deployment, adoption, or
production readiness.
