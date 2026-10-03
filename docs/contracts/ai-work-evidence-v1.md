# `ai-work-evidence/v1`

Forgeyard owns the public validation reference for the portfolio suite's small evidence handoff.
The contract lets ChatLens, Atlas, and Forgeyard exchange bounded synthetic evidence without
sharing raw transcripts, prompts, credentials, private paths, or provider metadata.

## Shape

```json
{
  "schema": "ai-work-evidence/v1",
  "evidence_id": "fixture-session:001",
  "source": "chatlens",
  "source_version": "0.3.0",
  "created_at": "2026-01-01T00:00:00Z",
  "subject": "synthetic release investigation",
  "summary": "bounded fixture evidence for a local review",
  "artifacts": [
    {"name": "trace.jsonl", "size": 42, "sha256": "<64 lowercase hex characters>"}
  ],
  "provenance": {"fixture": "portfolio-suite-v2"},
  "status": "verified"
}
```

`status` is one of `observed`, `verified`, `failed`, or `unknown`. Artifact names are bounded
repository-relative names; artifact contents remain in the owning tool's output file. The
canonical digest is SHA-256 over sorted-key, compact UTF-8 JSON plus a trailing newline.

Unknown fields and future schema versions are rejected. Validation is dependency-free and local.
The contract proves that a bounded evidence document is structurally valid; it does not prove a
provider call, deployment, user-visible outcome, or live repository state.

## Python reference

```python
from forgeyard.interop import build_evidence, evidence_digest

evidence = build_evidence(
    evidence_id="fixture-session:001",
    source="chatlens",
    source_version="0.3.0",
    created_at="2026-01-01T00:00:00Z",
    subject="synthetic release investigation",
    summary="bounded fixture evidence for a local review",
    status="verified",
    provenance={"fixture": "portfolio-suite-v2"},
)
print(evidence_digest(evidence))
```

The module is the reference validator. Other repositories should project their existing public
artifacts into this shape rather than copying raw source records or changing their own schemas.
