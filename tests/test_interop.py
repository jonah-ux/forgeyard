import json
from pathlib import Path

import pytest

from forgeyard.interop import (
    INTEROP_SCHEMA,
    artifact_from_path,
    build_evidence,
    canonical_bytes,
    evidence_digest,
    validate_evidence,
    write_evidence,
)


def fixture_evidence(**overrides):
    values = {
        "evidence_id": "fixture-session:001",
        "source": "chatlens",
        "source_version": "0.3.0",
        "created_at": "2026-01-01T00:00:00Z",
        "subject": "synthetic release investigation",
        "summary": "bounded fixture evidence for a local review",
        "status": "verified",
        "provenance": {"fixture": "portfolio-suite-v2"},
    }
    values.update(overrides)
    return build_evidence(**values)


def test_interop_document_is_canonical_and_digest_stable():
    document = fixture_evidence()
    reordered = json.loads(json.dumps(document))
    assert canonical_bytes(document) == canonical_bytes(reordered)
    assert evidence_digest(document) == evidence_digest(reordered)
    assert document["schema"] == INTEROP_SCHEMA


def test_artifact_from_path_records_bytes_without_embedding_contents(tmp_path: Path):
    source = tmp_path / "trace.jsonl"
    source.write_text("synthetic only\n", encoding="utf-8")
    artifact = artifact_from_path(source)
    evidence = fixture_evidence(artifacts=[artifact])
    assert evidence["artifacts"][0]["size"] == len("synthetic only\n".encode())
    assert "synthetic only" not in json.dumps(evidence)


def test_write_evidence_round_trips_canonical_document(tmp_path: Path):
    destination = tmp_path / "evidence.json"
    document = fixture_evidence()
    digest = write_evidence(document, destination)
    assert json.loads(destination.read_text(encoding="utf-8")) == document
    assert digest == evidence_digest(document)


def test_public_fixture_is_valid_and_canonical():
    fixture = Path(__file__).parent / "fixtures" / "portfolio-suite-v2" / "ai-work-evidence-v1.json"
    document = json.loads(fixture.read_text(encoding="utf-8"))
    assert validate_evidence(document) == document
    assert fixture.read_bytes() == canonical_bytes(document)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema", "ai-work-evidence/v2", "unsupported"),
        ("status", "complete", "status"),
        ("evidence_id", "../private", "evidence_id"),
        ("source", "private-system", "source"),
        ("created_at", "2026-01-01", "RFC 3339"),
    ],
)
def test_validation_rejects_ambiguous_documents(field, value, message):
    document = fixture_evidence()
    document[field] = value
    with pytest.raises(ValueError, match=message):
        validate_evidence(document)


def test_validation_rejects_unknown_fields_and_duplicate_artifacts(tmp_path: Path):
    document = fixture_evidence(extra="secret")
    with pytest.raises(ValueError, match="unknown fields"):
        validate_evidence(document)
    artifact = {"name": "trace.jsonl", "size": 1, "sha256": "0" * 64}
    with pytest.raises(ValueError, match="duplicate"):
        validate_evidence(fixture_evidence(artifacts=[artifact, artifact]))
    with pytest.raises(ValueError, match="provenance hash"):
        validate_evidence(fixture_evidence(provenance={"receipt_sha256": "bad"}))
