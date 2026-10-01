from pathlib import Path
import subprocess

from forgeyard.core import Evidence, EvidenceStatus, TaskRecord, TaskStatus, WorktreeError, build_review_packet, create_worktree, plan_worktree, verify_record, write_record


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
    verified = verify_record(output)
    assert verified["reviewable"] is True
    assert verified["sha256"] == digest
    assert verify_record(output, digest)["sha256"] == digest
    try:
        verify_record(output, "0" * 64)
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("mismatched digest was accepted")


def test_record_verifier_rejects_contradictory_status(tmp_path: Path):
    output = tmp_path / "blocked.json"
    output.write_text('{"task_id":"x","repository":"r","request":"q","status":"complete","evidence":[]}', encoding="utf-8")
    try:
        verify_record(output)
    except ValueError as exc:
        assert "contradicts" in str(exc)
    else:
        raise AssertionError("contradictory record was accepted")


def test_review_packet_requires_passing_evidence():
    record = TaskRecord("task-3", "fixture-repo", "review the change")
    record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "3 passed", "abc123"))
    record.finalize()
    packet = build_review_packet(record, "abc123", ["src/change.py", "tests/test_change.py"])
    assert packet["schema"] == "forgeyard-review-packet/v1"
    assert packet["changed_paths"] == ["src/change.py", "tests/test_change.py"]


def test_review_packet_refuses_blocked_record():
    record = TaskRecord("task-4", "fixture-repo", "review the change")
    record.add_evidence(Evidence("tests", EvidenceStatus.UNKNOWN, "not run"))
    record.finalize()
    try:
        build_review_packet(record, "abc123", ["src/change.py"])
    except ValueError as exc:
        assert "passing evidence" in str(exc)
    else:
        raise AssertionError("blocked evidence produced a review packet")


def test_review_packet_refuses_ambiguous_or_traversal_paths():
    record = TaskRecord("task-paths", "fixture-repo", "review the change")
    record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "3 passed", "abc123"))
    record.finalize()
    for paths in ([], ["../secret.txt"], ["src//change.py"], ["src\\change.py"]):
        try:
            build_review_packet(record, "abc123", paths)
        except ValueError as exc:
            assert "repository-relative" in str(exc)
        else:
            raise AssertionError(f"unsafe changed paths were accepted: {paths!r}")


def test_review_packet_digest_pin_rejects_changed_record(tmp_path: Path):
    record = TaskRecord("task-5", "fixture-repo", "review the change")
    record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "3 passed", "abc123"))
    record.finalize()
    output = tmp_path / "task.json"
    digest = write_record(record, output)
    output.write_text(output.read_text(encoding="utf-8").replace("review the change", "tampered request"), encoding="utf-8")
    try:
        verify_record(output, digest)
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("tampered record passed the review digest pin")


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
