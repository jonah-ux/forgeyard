"""Public, loss-aware evidence exchange for the portfolio suite.

The interop document is deliberately smaller than a Forgeyard task record. It
contains enough identity and verification information for another local tool to
consume, while leaving raw reports and task details at their owning source.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


INTEROP_SCHEMA = "ai-work-evidence/v1"
_STATUSES = frozenset({"observed", "verified", "failed", "unknown"})
_SOURCES = frozenset({"atlas", "chatlens", "forgeyard"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EVIDENCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_ALLOWED_KEYS = frozenset(
    {"schema", "evidence_id", "source", "source_version", "created_at", "subject", "summary", "artifacts", "provenance", "status"}
)


def canonical_bytes(document: Mapping[str, Any]) -> bytes:
    """Return the stable UTF-8 representation used for evidence digests."""

    return (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def artifact_from_path(path: Path, name: str | None = None) -> dict[str, Any]:
    """Describe a regular local artifact without embedding its contents."""

    if path.is_symlink() or not path.is_file():
        raise ValueError("interop artifacts must be regular files")
    payload = path.read_bytes()
    artifact_name = name or path.name
    _validate_name(artifact_name, "artifact name")
    return {"name": artifact_name, "size": len(payload), "sha256": sha256_bytes(payload)}


def build_evidence(
    *,
    evidence_id: str,
    source: str,
    source_version: str,
    created_at: str,
    subject: str,
    summary: str,
    status: str,
    artifacts: list[Mapping[str, Any]] | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate one public-safe evidence document."""

    document = {
        "schema": INTEROP_SCHEMA,
        "evidence_id": evidence_id,
        "source": source,
        "source_version": source_version,
        "created_at": created_at,
        "subject": subject,
        "summary": summary,
        "artifacts": list(artifacts or []),
        "provenance": dict(provenance or {}),
        "status": status,
    }
    return validate_evidence(document)


def validate_evidence(document: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on malformed, future, or privacy-ambiguous documents."""

    if not isinstance(document, Mapping):
        raise ValueError("interop evidence must be a JSON object")
    unknown = set(document) - _ALLOWED_KEYS
    if unknown:
        raise ValueError(f"interop evidence contains unknown fields: {sorted(unknown)}")
    required = _ALLOWED_KEYS - {"artifacts", "provenance"}
    missing = sorted(key for key in required if key not in document)
    if missing:
        raise ValueError(f"interop evidence is missing required fields: {', '.join(missing)}")
    if document["schema"] != INTEROP_SCHEMA:
        raise ValueError("unsupported interop evidence schema")
    _validate_identifier(document["evidence_id"], _EVIDENCE_ID_RE, "evidence_id")
    if document["source"] not in _SOURCES:
        raise ValueError("interop evidence source is not supported")
    for key in ("source_version", "subject", "summary"):
        value = document[key]
        if not isinstance(value, str) or not value.strip() or len(value) > 2048:
            raise ValueError(f"interop evidence {key} must be a bounded non-empty string")
    created_at = document["created_at"]
    if not isinstance(created_at, str) or not created_at.endswith("Z"):
        raise ValueError("interop evidence created_at must be an RFC 3339 UTC timestamp")
    try:
        datetime.fromisoformat(created_at[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("interop evidence created_at must be an RFC 3339 UTC timestamp") from exc
    if document["status"] not in _STATUSES:
        raise ValueError("interop evidence status is invalid")
    artifacts = document.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("interop evidence artifacts must be a list")
    seen: set[str] = set()
    normalized_artifacts: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or set(artifact) != {"name", "size", "sha256"}:
            raise ValueError("interop artifact must contain only name, size, and sha256")
        name = artifact["name"]
        _validate_name(name, "artifact name")
        if name in seen:
            raise ValueError(f"duplicate interop artifact name: {name}")
        seen.add(name)
        size = artifact["size"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("interop artifact size must be a non-negative integer")
        digest = artifact["sha256"]
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise ValueError("interop artifact sha256 must be lowercase hexadecimal")
        normalized_artifacts.append({"name": name, "size": size, "sha256": digest})
    provenance = document.get("provenance", {})
    if not isinstance(provenance, Mapping):
        raise ValueError("interop evidence provenance must be an object")
    normalized_provenance = dict(provenance)
    for key, value in normalized_provenance.items():
        if not isinstance(key, str) or not isinstance(value, (str, int, bool, type(None))):
            raise ValueError("interop provenance values must be scalar")
        if key.endswith("_sha256") and (not isinstance(value, str) or not _SHA256_RE.fullmatch(value)):
            raise ValueError(f"interop provenance hash is invalid: {key}")
    return {
        "schema": INTEROP_SCHEMA,
        "evidence_id": document["evidence_id"],
        "source": document["source"],
        "source_version": document["source_version"],
        "created_at": created_at,
        "subject": document["subject"],
        "summary": document["summary"],
        "artifacts": normalized_artifacts,
        "provenance": normalized_provenance,
        "status": document["status"],
    }


def evidence_digest(document: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(validate_evidence(document)))


def write_evidence(document: Mapping[str, Any], destination: Path) -> str:
    normalized = validate_evidence(document)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical_bytes(normalized))
    return evidence_digest(normalized)


def _validate_identifier(value: Any, pattern: re.Pattern[str], label: str) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"interop {label} has an invalid format")


def _validate_name(value: Any, label: str) -> None:
    _validate_identifier(value, _NAME_RE, label)
    if ".." in value or value.startswith("/") or "\\" in value:
        raise ValueError(f"interop {label} must be repository-relative")
