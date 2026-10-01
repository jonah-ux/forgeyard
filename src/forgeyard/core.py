"""Framework-free task and evidence contracts for the Forgeyard baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
from pathlib import Path
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
