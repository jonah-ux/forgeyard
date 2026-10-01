from pathlib import Path
import subprocess

from forgeyard.core import Evidence, EvidenceStatus, TaskRecord, TaskStatus, WorktreeError, create_worktree, plan_worktree, write_record


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
    assert command[0:2] == ["git", "-C"]
    assert Path(command[2]).resolve() == source.resolve()
    assert command[3:5] == ["worktree", "add"]
    assert command[-1] == "main"
    assert "--detach" in command
    assert Path(command[6]).resolve() == (tmp_path / "task").resolve()


def test_create_worktree_materializes_detached_checkout(tmp_path: Path):
    source = tmp_path / "repo"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "forgeyard@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Forgeyard Fixture"], check=True)
    (source / "README.md").write_text("fixture\n")
    subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
    destination = tmp_path / "worktree"
    create_worktree(plan_worktree(source, destination))
    assert (destination / "README.md").read_text() == "fixture\n"
    result = subprocess.run(["git", "-C", str(destination), "symbolic-ref", "--quiet", "--short", "HEAD"], capture_output=True, text=True)
    assert result.returncode != 0
