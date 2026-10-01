from pathlib import Path

from forgeyard.core import Evidence, EvidenceStatus, TaskRecord, TaskStatus, write_record


def test_failed_evidence_blocks_completion():
    record = TaskRecord("task-1", "fixture-repo", "add a feature")
    record.add_evidence(Evidence("tests", EvidenceStatus.FAIL, "one assertion failed"))
    record.finalize()
    assert record.status is TaskStatus.BLOCKED
    assert not record.ready_for_review()


def test_all_pass_evidence_produces_reviewable_record(tmp_path: Path):
    record = TaskRecord("task-2", "fixture-repo", "add a feature")
    record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "3 passed", "abc123"))
    record.add_evidence(Evidence("diff", EvidenceStatus.PASS, "clean diff", "abc123"))
    record.finalize()
    output = tmp_path / "task.json"
    digest = write_record(record, output)
    assert record.status is TaskStatus.READY_FOR_REVIEW
    assert len(digest) == 64
    assert '"status": "ready_for_review"' in output.read_text()
