from pathlib import Path

from forgeyard.core import Evidence, EvidenceStatus, TaskRecord, TaskStatus, WorktreeError, plan_worktree, write_record


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


def test_worktree_plan_refuses_destination_inside_source(tmp_path: Path):
    source = tmp_path / "repo"
    (source / ".git").mkdir(parents=True)
    try:
        plan_worktree(source, source / ".worktrees" / "task")
    except WorktreeError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("unsafe nested destination was admitted")


def test_worktree_plan_is_argument_safe(tmp_path: Path):
    source = tmp_path / "repo"
    (source / ".git").mkdir(parents=True)
    plan = plan_worktree(source, tmp_path / "task", "main")
    command = plan.command()
    assert command[0:5] == ["git", "-C", str(source), "worktree", "add"]
    assert command[-1] == "main"
    assert "--detach" in command
    assert Path(command[6]).resolve() == (tmp_path / "task").resolve()
