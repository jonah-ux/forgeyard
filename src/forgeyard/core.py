"""Framework-free task and evidence contracts for the Forgeyard baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any


class EvidenceStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"


class TaskStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"
    COMPLETE = "complete"


@dataclass(frozen=True)
class Evidence:
    name: str
    status: EvidenceStatus
    detail: str
    revision: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "revision": self.revision,
        }


@dataclass
class TaskRecord:
    task_id: str
    repository: str
    request: str
    status: TaskStatus = TaskStatus.CREATED
    evidence: list[Evidence] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    def add_evidence(self, evidence: Evidence) -> None:
        if not evidence.name.strip():
            raise ValueError("evidence name must be non-empty")
        if any(item.name == evidence.name for item in self.evidence):
            raise ValueError(f"duplicate evidence name: {evidence.name}")
        self.evidence.append(evidence)
        if evidence.status is EvidenceStatus.FAIL:
            self.status = TaskStatus.BLOCKED

    def ready_for_review(self) -> bool:
        if self.status is TaskStatus.BLOCKED or not self.evidence:
            return False
        return all(item.status is EvidenceStatus.PASS for item in self.evidence)

    def finalize(self) -> None:
        self.status = TaskStatus.READY_FOR_REVIEW if self.ready_for_review() else TaskStatus.BLOCKED

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "repository": self.repository,
            "request": self.request,
            "status": self.status.value,
            "evidence": [item.as_dict() for item in self.evidence],
            "artifacts": list(self.artifacts),
        }


def write_record(record: TaskRecord, destination: Path) -> str:
    """Write a stable JSON record and return its content hash."""

    payload = json.dumps(record.as_dict(), indent=2, sort_keys=True) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evidence_from_report(source: Path, name: str, revision: str | None = None) -> Evidence:
    """Convert a specialist JSON report into bounded Forgeyard evidence.

    Reports must expose a boolean ``ok`` field. Only the schema label and boolean
    result enter the task record; raw report details stay in the source file.
    """

    if not name.strip():
        raise ValueError("report evidence name must be non-empty")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid specialist report: {source}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
        raise ValueError(f"specialist report must contain boolean ok: {source}")
    schema = payload.get("schema", "unknown")
    if not isinstance(schema, str) or not schema:
        schema = "unknown"
    status = EvidenceStatus.PASS if payload["ok"] else EvidenceStatus.FAIL
    detail = f"schema={schema}; ok={str(payload['ok']).lower()}"
    return Evidence(name=name, status=status, detail=detail, revision=revision)


class WorktreeError(ValueError):
    """A worktree request cannot be safely admitted."""


def read_record(source: Path) -> TaskRecord:
    """Load a task record and reject malformed or contradictory state."""

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        return _record_from_payload(payload, source)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Forgeyard record: {source}") from exc


def _record_from_payload(payload: Any, source: Path | str) -> TaskRecord:
    try:
        if not isinstance(payload, dict):
            raise ValueError("record must be a JSON object")
        evidence = [
            Evidence(
                name=str(item["name"]),
                status=EvidenceStatus(item["status"]),
                detail=str(item["detail"]),
                revision=item.get("revision"),
            )
            for item in payload["evidence"]
        ]
        record = TaskRecord(
            task_id=str(payload["task_id"]),
            repository=str(payload["repository"]),
            request=str(payload["request"]),
            status=TaskStatus(payload["status"]),
            evidence=evidence,
            artifacts=[str(value) for value in payload.get("artifacts", [])],
        )
        if any(not item.name.strip() for item in evidence):
            raise ValueError("invalid Forgeyard record: evidence name must be non-empty")
        names = [item.name for item in evidence]
        if len(names) != len(set(names)):
            raise ValueError("invalid Forgeyard record: duplicate evidence name")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid Forgeyard record: {source}") from exc
    expected = TaskStatus.READY_FOR_REVIEW if record.ready_for_review() else TaskStatus.BLOCKED
    if record.status not in {expected, TaskStatus.CREATED, TaskStatus.RUNNING}:
        raise ValueError(f"record status contradicts evidence: {record.status.value} vs {expected.value}")
    return record


def verify_record(source: Path, expected_sha256: str | None = None) -> dict[str, Any]:
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"record digest mismatch: expected {expected_sha256}, got {digest}")
    record = read_record(source)
    return {
        "schema": "forgeyard-record-verify/v1",
        "record": str(source),
        "sha256": digest,
        "task_id": record.task_id,
        "status": record.status.value,
        "evidence_count": len(record.evidence),
        "reviewable": record.ready_for_review(),
    }


def build_review_packet(record: TaskRecord, revision: str, changed_paths: list[str]) -> dict[str, Any]:
    """Combine a reviewable record with the exact revision and changed paths."""

    if not record.ready_for_review():
        raise ValueError("review packet requires a record with only passing evidence")
    evidence_revisions = {item.revision for item in record.evidence if item.revision}
    if evidence_revisions and evidence_revisions != {revision}:
        raise ValueError("review packet revision does not match evidence revisions")
    if not revision or not changed_paths or any(
        not isinstance(path, str)
        or not path
        or path.startswith(("/", "\\"))
        or "\\" in path
        or any(part in ("", ".", "..") for part in path.split("/"))
        for path in changed_paths
    ):
        raise ValueError("review packet requires a revision and repository-relative changed paths")
    return {
        "schema": "forgeyard-review-packet/v1",
        "task_id": record.task_id,
        "repository": record.repository,
        "request": record.request,
        "revision": revision,
        "changed_paths": sorted(set(changed_paths)),
        "evidence": [item.as_dict() for item in record.evidence],
        "artifacts": list(record.artifacts),
        "reviewable": True,
    }


_PROVENANCE_PACKET_SCHEMA = "forgeyard-provenance-packet/v1"
_PROVENANCE_VERIFY_SCHEMA = "forgeyard-provenance-packet-verify/v1"
_RECEIPT_SCHEMA = "forgeyard-evidence-receipt/v1"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _packet_sha256(payload: dict[str, Any]) -> str:
    return _sha256(_canonical_json(payload).encode("utf-8"))


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _validate_relative_source_path(value: Any) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValueError("provenance source paths must be non-empty repository-relative paths")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("provenance source paths must not contain empty, '.' or '..' segments")
    return value


def _source_file(root: Path, relative: str) -> Path:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"source root is not a directory: {root}")
    relative = _validate_relative_source_path(relative)
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError(f"provenance source cannot be a symlink: {relative}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"provenance source escapes source root: {relative}") from exc
    if not candidate.is_file():
        raise ValueError(f"provenance source is not a regular file: {relative}")
    if candidate.stat().st_nlink != 1:
        raise ValueError(f"provenance source cannot be a hardlink: {relative}")
    return candidate


def _source_entry(root: Path, relative: str) -> dict[str, Any]:
    path = _source_file(root, relative)
    payload = path.read_bytes()
    return {"path": relative, "sha256": _sha256(payload), "size": len(payload)}


def _read_receipt(source: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        if source.is_symlink() or not source.is_file() or source.stat().st_nlink != 1:
            raise ValueError(f"evidence receipt must be a regular, unlinked file: {source}")
        raw = source.read_bytes()
        text = raw.decode("utf-8")
        payload = json.loads(text)
    except (OSError, UnicodeDecodeError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Forgeyard evidence receipt: {source}") from exc
    return raw, _validate_receipt_payload(payload, source)


def write_evidence_receipt(
    record_source: Path,
    evidence_name: str,
    source_paths: list[str],
    destination: Path,
) -> str:
    """Write one explicit evidence receipt bound to a saved task record."""

    if not evidence_name:
        raise ValueError("evidence receipt requires a name")
    normalized_paths = [_validate_relative_source_path(path) for path in source_paths]
    if not normalized_paths or len(set(normalized_paths)) != len(normalized_paths):
        raise ValueError("evidence receipt source paths must be sorted and unique")
    normalized_paths = sorted(normalized_paths)
    record = read_record(record_source)
    matches = [item for item in record.evidence if item.name == evidence_name]
    if len(matches) != 1:
        raise ValueError(f"evidence name is not unique in task record: {evidence_name}")
    evidence = matches[0]
    payload = {
        "schema": _RECEIPT_SCHEMA,
        "task_id": record.task_id,
        "name": evidence.name,
        "status": evidence.status.value,
        "detail": evidence.detail,
        "revision": evidence.revision,
        "source_paths": normalized_paths,
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    destination = destination.expanduser()
    if destination.is_symlink():
        raise ValueError(f"refusing to overwrite symlink output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(encoded, encoding="utf-8")
    return _sha256(encoded.encode("utf-8"))


def _validate_receipt_payload(payload: Any, source: Path | str) -> dict[str, Any]:
    required = {"schema", "task_id", "name", "status", "detail", "revision", "source_paths"}
    if not isinstance(payload, dict) or set(payload) != required or payload.get("schema") != _RECEIPT_SCHEMA:
        raise ValueError(f"invalid Forgeyard evidence receipt: {source}")
    for field_name in ("task_id", "name", "detail"):
        if not isinstance(payload[field_name], str) or not payload[field_name]:
            raise ValueError(f"invalid Forgeyard evidence receipt field: {field_name}")
    if payload["status"] not in {status.value for status in EvidenceStatus}:
        raise ValueError(f"invalid Forgeyard evidence receipt status: {source}")
    if payload["revision"] is not None and (not isinstance(payload["revision"], str) or not payload["revision"]):
        raise ValueError(f"invalid Forgeyard evidence receipt revision: {source}")
    paths = payload["source_paths"]
    if not isinstance(paths, list) or not paths:
        raise ValueError(f"evidence receipt requires source paths: {source}")
    normalized = [_validate_relative_source_path(path) for path in paths]
    if normalized != sorted(set(normalized)):
        raise ValueError(f"evidence receipt source paths must be sorted and unique: {source}")
    return payload


def _read_record_bytes(source: Path) -> tuple[bytes, dict[str, Any], TaskRecord]:
    try:
        raw = source.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Forgeyard record: {source}") from exc
    record = _record_from_payload(payload, source)
    return raw, payload, record


def _receipt_entries(
    record: TaskRecord,
    receipt_sources: list[Path],
    revision: str,
    changed_paths: list[str],
) -> list[dict[str, Any]]:
    expected = {item.name: item for item in record.evidence}
    if len(expected) != len(record.evidence):
        raise ValueError("provenance packet requires unique evidence names")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    allowed_paths = set(changed_paths)
    for source in receipt_sources:
        raw, receipt = _read_receipt(source)
        name = receipt["name"]
        if name in seen:
            raise ValueError(f"duplicate evidence receipt: {name}")
        seen.add(name)
        evidence = expected.get(name)
        if evidence is None:
            raise ValueError(f"evidence receipt is not present in task record: {name}")
        if receipt["task_id"] != record.task_id or receipt["status"] != evidence.status.value:
            raise ValueError(f"evidence receipt does not match task record: {name}")
        if receipt["detail"] != evidence.detail or receipt["revision"] != evidence.revision:
            raise ValueError(f"evidence receipt provenance does not match task record: {name}")
        if receipt["revision"] is not None and receipt["revision"] != revision:
            raise ValueError(f"evidence receipt revision does not match packet revision: {name}")
        if not set(receipt["source_paths"]).issubset(allowed_paths):
            raise ValueError(f"evidence receipt references an unsealed source path: {name}")
        entries.append(
            {
                "sha256": _sha256(raw),
                "raw": raw.decode("utf-8"),
                "payload": receipt,
            }
        )
    if seen != set(expected):
        missing = sorted(set(expected) - seen)
        raise ValueError(f"missing evidence receipts: {', '.join(missing)}")
    if any(entry["payload"]["status"] != EvidenceStatus.PASS.value for entry in entries):
        raise ValueError("provenance packet requires only passing evidence receipts")
    return sorted(entries, key=lambda entry: entry["payload"]["name"])


def build_provenance_packet(
    record_source: Path,
    receipt_sources: list[Path],
    source_root: Path,
    revision: str,
    changed_paths: list[str],
) -> dict[str, Any]:
    """Build a portable packet containing records, receipts, and source-byte seals."""

    if not revision:
        raise ValueError("provenance packet requires a revision")
    if not changed_paths:
        raise ValueError("provenance packet requires at least one source path")
    normalized_paths = [_validate_relative_source_path(path) for path in changed_paths]
    if len(set(normalized_paths)) != len(normalized_paths):
        raise ValueError("provenance source paths must be sorted and unique")
    normalized_paths = sorted(normalized_paths)
    raw_record, record_payload, record = _read_record_bytes(record_source)
    review = build_review_packet(record, revision, normalized_paths)
    receipts = _receipt_entries(record, receipt_sources, revision, normalized_paths)
    sources = [_source_entry(source_root, path) for path in normalized_paths]
    unsigned = {
        "schema": _PROVENANCE_PACKET_SCHEMA,
        "revision": revision,
        "task_id": record.task_id,
        "repository": record.repository,
        "request": record.request,
        "changed_paths": normalized_paths,
        "record": {
            "sha256": _sha256(raw_record),
            "raw": raw_record.decode("utf-8"),
            "payload": record_payload,
        },
        "receipts": receipts,
        "sources": sources,
        "reviewable": review["reviewable"],
    }
    return {**unsigned, "packet_sha256": _packet_sha256(unsigned)}


def _atomic_json_write(destination: Path, payload: dict[str, Any]) -> None:
    destination = destination.expanduser()
    if destination.is_symlink():
        raise ValueError(f"refusing to overwrite symlink output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
        Path(temporary).replace(destination)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def write_provenance_packet(
    record_source: Path,
    receipt_sources: list[Path],
    source_root: Path,
    revision: str,
    changed_paths: list[str],
    destination: Path,
) -> str:
    """Write a portable provenance packet atomically and return its seal."""

    packet = build_provenance_packet(record_source, receipt_sources, source_root, revision, changed_paths)
    _atomic_json_write(destination, packet)
    return packet["packet_sha256"]


def _validate_provenance_packet(payload: Any, source: Path) -> dict[str, Any]:
    required = {
        "schema", "revision", "task_id", "repository", "request", "changed_paths",
        "record", "receipts", "sources", "reviewable", "packet_sha256",
    }
    if not isinstance(payload, dict) or set(payload) != required or payload.get("schema") != _PROVENANCE_PACKET_SCHEMA:
        raise ValueError(f"invalid Forgeyard provenance packet: {source}")
    unsigned = dict(payload)
    digest = unsigned.pop("packet_sha256")
    if not isinstance(digest, str) or digest != _packet_sha256(unsigned):
        raise ValueError(f"provenance packet digest mismatch: {source}")
    for field_name in ("revision", "task_id", "repository", "request"):
        if not isinstance(payload[field_name], str) or not payload[field_name]:
            raise ValueError(f"invalid provenance packet field: {field_name}")
    paths = payload["changed_paths"]
    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise ValueError(f"invalid provenance packet source paths: {source}")
    if paths != sorted(set(paths)):
        raise ValueError(f"provenance packet paths are not sorted and unique: {source}")
    normalized_paths = [_validate_relative_source_path(path) for path in paths]
    if normalized_paths != paths:
        raise ValueError(f"invalid provenance packet source path: {source}")
    record = payload["record"]
    if not isinstance(record, dict) or set(record) != {"sha256", "raw", "payload"}:
        raise ValueError(f"invalid provenance packet record: {source}")
    if not isinstance(record["raw"], str) or not isinstance(record["payload"], dict) or not _is_sha256(record["sha256"]) or _sha256(record["raw"].encode("utf-8")) != record["sha256"]:
        raise ValueError(f"provenance packet record bytes mismatch: {source}")
    try:
        parsed_record = json.loads(record["raw"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid provenance packet record JSON: {source}") from exc
    if parsed_record != record["payload"]:
        raise ValueError(f"provenance packet record payload mismatch: {source}")
    _record_from_payload(parsed_record, source)
    receipts = payload["receipts"]
    if not isinstance(receipts, list) or not receipts:
        raise ValueError(f"provenance packet requires evidence receipts: {source}")
    names: list[str] = []
    for entry in receipts:
        if not isinstance(entry, dict) or set(entry) != {"sha256", "raw", "payload"}:
            raise ValueError(f"invalid provenance packet receipt: {source}")
        if not isinstance(entry["raw"], str) or not isinstance(entry["payload"], dict) or not _is_sha256(entry["sha256"]) or _sha256(entry["raw"].encode("utf-8")) != entry["sha256"]:
            raise ValueError(f"provenance packet receipt bytes mismatch: {source}")
        try:
            parsed_receipt = json.loads(entry["raw"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid provenance packet receipt JSON: {source}") from exc
        if parsed_receipt != entry["payload"]:
            raise ValueError(f"provenance packet receipt payload mismatch: {source}")
        receipt = _validate_receipt_payload(parsed_receipt, source)
        names.append(receipt["name"])
    if names != sorted(set(names)):
        raise ValueError(f"provenance packet receipts are not sorted and unique: {source}")
    sources = payload["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"provenance packet requires source-byte seals: {source}")
    source_paths: list[str] = []
    for entry in sources:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size"}:
            raise ValueError(f"invalid provenance packet source seal: {source}")
        path = _validate_relative_source_path(entry["path"])
        if not _is_sha256(entry["sha256"]):
            raise ValueError(f"invalid provenance packet source digest: {source}")
        if not isinstance(entry["size"], int) or isinstance(entry["size"], bool) or entry["size"] < 0:
            raise ValueError(f"invalid provenance packet source size: {source}")
        source_paths.append(path)
    if source_paths != sorted(set(source_paths)) or source_paths != paths:
        raise ValueError(f"provenance packet source seals do not match changed paths: {source}")
    if not isinstance(payload["reviewable"], bool):
        raise ValueError(f"invalid provenance packet reviewable flag: {source}")
    return payload


def read_provenance_packet(source: Path) -> dict[str, Any]:
    """Load and validate a portable provenance packet and its self-seal."""

    try:
        return _validate_provenance_packet(json.loads(source.read_text(encoding="utf-8")), source)
    except (OSError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Forgeyard provenance packet: {source}") from exc


def verify_provenance_packet(source: Path, source_root: Path | None = None) -> dict[str, Any]:
    """Verify packet integrity, receipt bindings, and current source-byte freshness."""

    try:
        packet = read_provenance_packet(source)
    except ValueError as exc:
        return {
            "schema": _PROVENANCE_VERIFY_SCHEMA,
            "packet": str(source),
            "valid": False,
            "fresh": False,
            "reviewable": False,
            "ok": False,
            "errors": [str(exc)],
        }
    errors: list[str] = []
    record = _record_from_payload(packet["record"]["payload"], source)
    if record.task_id != packet["task_id"] or record.repository != packet["repository"] or record.request != packet["request"]:
        errors.append("provenance packet task fields do not match embedded record")
    if not record.ready_for_review() or not packet["reviewable"]:
        errors.append("provenance packet is not reviewable")
    evidence = {item.name: item for item in record.evidence}
    receipt_names: set[str] = set()
    for entry in packet["receipts"]:
        receipt = entry["payload"]
        name = receipt["name"]
        receipt_names.add(name)
        expected = evidence.get(name)
        if expected is None:
            errors.append(f"receipt is not present in task record: {name}")
            continue
        if receipt["task_id"] != record.task_id or receipt["status"] != expected.status.value or receipt["detail"] != expected.detail or receipt["revision"] != expected.revision:
            errors.append(f"receipt does not match task evidence: {name}")
        if receipt["status"] != EvidenceStatus.PASS.value:
            errors.append(f"receipt is not passing: {name}")
        if receipt["revision"] is not None and receipt["revision"] != packet["revision"]:
            errors.append(f"receipt revision mismatch: {name}")
        if not set(receipt["source_paths"]).issubset(set(packet["changed_paths"])):
            errors.append(f"receipt references an unsealed source path: {name}")
    if receipt_names != set(evidence):
        errors.append("receipt set does not exactly match task evidence")
    semantic_errors = list(errors)
    source_errors: list[str] = []
    freshness = "unknown"
    if source_root is not None:
        freshness = "matched"
        for entry in packet["sources"]:
            try:
                current = _source_entry(source_root, entry["path"])
            except ValueError as exc:
                source_errors.append(str(exc))
                continue
            if current != entry:
                source_errors.append(f"source bytes changed: {entry['path']}")
    errors.extend(source_errors)
    valid = not semantic_errors
    fresh = source_root is not None and not source_errors
    reviewable = valid and packet["reviewable"]
    return {
        "schema": _PROVENANCE_VERIFY_SCHEMA,
        "packet": str(source),
        "packet_sha256": packet["packet_sha256"],
        "revision": packet["revision"],
        "source_count": len(packet["sources"]),
        "receipt_count": len(packet["receipts"]),
        "freshness": freshness if not source_errors else "mismatch",
        "valid": valid,
        "fresh": fresh,
        "reviewable": reviewable,
        "ok": valid and fresh and reviewable,
        "errors": errors,
    }


@dataclass(frozen=True)
class WorktreePlan:
    source: Path
    destination: Path
    revision: str

    def command(self) -> list[str]:
        return ["git", "-C", str(self.source), "worktree", "add", "--detach", str(self.destination), self.revision]


def plan_worktree(source: Path, destination: Path, revision: str = "HEAD") -> WorktreePlan:
    """Validate a worktree request without touching the filesystem."""

    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not (source / ".git").exists() and not (source / "HEAD").exists():
        raise WorktreeError(f"source is not a Git checkout: {source}")
    if destination == source or source in destination.parents:
        raise WorktreeError("destination must be outside the source checkout")
    if destination.exists():
        raise WorktreeError(f"destination already exists: {destination}")
    if not revision or revision.startswith("-"):
        raise WorktreeError("revision must be a non-empty Git revision")
    return WorktreePlan(source, destination, revision)


def create_worktree(plan: WorktreePlan, timeout: float = 20.0) -> None:
    """Create one detached worktree with bounded, argument-safe Git execution."""

    plan.destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(plan.command(), check=True, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorktreeError(f"worktree creation failed: {exc}") from exc
