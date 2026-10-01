"""Framework-free task and evidence contracts for the Forgeyard baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import subprocess
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


class WorktreeError(ValueError):
    """A worktree request cannot be safely admitted."""


def read_record(source: Path) -> TaskRecord:
    """Load a task record and reject malformed or contradictory state."""

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
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
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
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
    if not revision or any(not path or path.startswith("/") for path in changed_paths):
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
