# Forgeyard interop conformance corpus

This directory is the synthetic compatibility target for `ai-work-evidence/v1`. The fixtures
contain no real transcripts, paths, credentials, or provider data. Each case records the expected
validator result and, for valid documents, the status Forgeyard should expose when composing it.

Run the deterministic report from the repository root:

```bash
python scripts/run_interop_conformance.py --json
```

The runner is a local compatibility check, not proof of deployment, adoption, or a user-visible
outcome. A consumer may mirror these fixtures for its own tests but should keep Forgeyard as the
reference validator for this contract.
