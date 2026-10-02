import json
from pathlib import Path
import subprocess

from forgeyard.cli import main
from forgeyard.core import (
    Evidence,
    EvidenceStatus,
    TaskRecord,
    TaskStatus,
    WorktreeError,
    build_provenance_packet,
    build_review_packet,
    create_worktree,
    evidence_from_report,
    plan_worktree,
    verify_provenance_packet,
    verify_record,
    write_evidence_receipt,
    write_provenance_packet,
    write_record,
)



def test_demo_command_runs_the_reviewable_walkthrough(capsys):
    assert main(["demo"]) == 0
    output = capsys.readouterr().out
    assert '"schema": "forgeyard-demo/v1"' in output
    assert '"reviewable": true' in output
    assert '"record_sha256"' in output


def test_compose_converts_specialist_reports_without_copying_payload(tmp_path: Path):
    report = tmp_path / "mcp.json"
    report.write_text(json.dumps({"schema": "mcp-doctor/v1", "ok": True, "findings": [{"secret": "never copy"}]}), encoding="utf-8")
    evidence = evidence_from_report(report, "contract", "abc123")
    assert evidence.status is EvidenceStatus.PASS
    assert evidence.detail == "schema=mcp-doctor/v1; ok=true"
    assert "never copy" not in evidence.detail


def test_compose_rejects_reports_without_boolean_result(tmp_path: Path):
    report = tmp_path / "bad.json"
    report.write_text('{"schema":"unknown"}', encoding="utf-8")
    try:
        evidence_from_report(report, "contract")
    except ValueError as exc:
        assert "boolean ok" in str(exc)
    else:
        raise AssertionError("unbounded specialist report was accepted")


def test_compose_accepts_agent_proof_interop_projection_without_copying_payload(tmp_path: Path):
    report = tmp_path / "context-interop.json"
    report.write_text(
        json.dumps(
            {
                "schema": "agent-proof/interop/v1",
                "projection": {"status": {"ok": True, "observed": True}},
                "answer": "private answer text",
            }
        ),
        encoding="utf-8",
    )
    evidence = evidence_from_report(report, "context", "abc123")
    assert evidence.status is EvidenceStatus.PASS
    assert evidence.detail == "schema=agent-proof/interop/v1; ok=true"
    assert "private answer text" not in evidence.detail


def test_compose_rejects_malformed_agent_proof_interop_projection(tmp_path: Path):
    report = tmp_path / "malformed-interop.json"
    report.write_text(
        json.dumps({"schema": "agent-proof/interop/v1", "projection": {"status": {"ok": "yes"}}}),
        encoding="utf-8",
    )
    try:
        evidence_from_report(report, "context")
    except ValueError as exc:
        assert "boolean ok" in str(exc)
    else:
        raise AssertionError("malformed interop projection was accepted")


def test_compose_command_writes_reviewable_record(tmp_path: Path, capsys):
    report = tmp_path / "doctor.json"
    output = tmp_path / "record.json"
    report.write_text(json.dumps({"schema": "mcp-doctor/v1", "ok": True}), encoding="utf-8")
    assert main(["compose", "--task-id", "compose-1", "--repository", "fixture", "--request", "check", "--input", f"contract={report}", "--output", str(output)]) == 0
    assert '"status": "ready_for_review"' in capsys.readouterr().out
    assert json.loads(output.read_text(encoding="utf-8"))["evidence"][0]["detail"] == "schema=mcp-doctor/v1; ok=true"

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


def test_review_packet_refuses_revision_mismatch():
    record = TaskRecord("task-revision", "fixture-repo", "review the change")
    record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "3 passed", "evidence-rev"))
    record.finalize()
    try:
        build_review_packet(record, "different-rev", ["src/change.py"])
    except ValueError as exc:
        assert "does not match evidence revisions" in str(exc)
    else:
        raise AssertionError("revision mismatch produced a review packet")


def test_record_refuses_ambiguous_evidence_names():
    record = TaskRecord("task-evidence", "fixture-repo", "review the change")
    record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "3 passed"))
    try:
        record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "also passed"))
    except ValueError as exc:
        assert "duplicate evidence name" in str(exc)
    else:
        raise AssertionError("duplicate evidence name was accepted")
    try:
        record.add_evidence(Evidence("  ", EvidenceStatus.PASS, "unnamed"))
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("empty evidence name was accepted")


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


def _write_provenance_fixture(tmp_path: Path) -> tuple[Path, Path, list[Path], str]:
    source_root = tmp_path / "repo"
    (source_root / "src").mkdir(parents=True)
    (source_root / "tests").mkdir()
    (source_root / "src" / "app.py").write_text("print('app')\n", encoding="utf-8")
    (source_root / "tests" / "test_app.py").write_text("def test_app(): pass\n", encoding="utf-8")
    revision = "abc123"
    record = TaskRecord("task-provenance", "fixture-repo", "ship the fixture")
    record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "pytest -q -> 1 passed", revision))
    record.add_evidence(Evidence("diff", EvidenceStatus.PASS, "clean diff", revision))
    record.finalize()
    record_path = tmp_path / "task.json"
    write_record(record, record_path)
    receipt_paths: list[Path] = []
    for evidence_name, paths in (
        ("tests", ["tests/test_app.py"]),
        ("diff", ["src/app.py"]),
    ):
        receipt_path = tmp_path / f"{evidence_name}.receipt.json"
        assert write_evidence_receipt(record_path, evidence_name, paths, receipt_path)
        receipt_paths.append(receipt_path)
    return source_root, record_path, receipt_paths, revision


def test_provenance_packet_embeds_records_receipts_and_source_seals(tmp_path: Path):
    source_root, record_path, receipt_paths, revision = _write_provenance_fixture(tmp_path)
    packet_path = tmp_path / "review.provenance.json"
    digest = write_provenance_packet(
        record_path,
        receipt_paths,
        source_root,
        revision,
        ["src/app.py", "tests/test_app.py"],
        packet_path,
    )
    packet = build_provenance_packet(record_path, receipt_paths, source_root, revision, ["src/app.py", "tests/test_app.py"])
    assert digest == packet["packet_sha256"]
    assert packet["schema"] == "forgeyard-provenance-packet/v1"
    assert packet["record"]["raw"]
    assert len(packet["receipts"]) == 2
    verified = verify_provenance_packet(packet_path, source_root)
    assert verified["ok"] is True
    assert verified["fresh"] is True
    assert verified["freshness"] == "matched"
    assert verified["reviewable"] is True


def test_provenance_packet_fails_closed_on_source_drift(tmp_path: Path):
    source_root, record_path, receipt_paths, revision = _write_provenance_fixture(tmp_path)
    packet_path = tmp_path / "review.provenance.json"
    write_provenance_packet(record_path, receipt_paths, source_root, revision, ["src/app.py", "tests/test_app.py"], packet_path)
    (source_root / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
    verified = verify_provenance_packet(packet_path, source_root)
    assert verified["ok"] is False
    assert verified["fresh"] is False
    assert any("source bytes changed" in error for error in verified["errors"])


def test_provenance_packet_requires_live_source_root(tmp_path: Path):
    source_root, record_path, receipt_paths, revision = _write_provenance_fixture(tmp_path)
    packet_path = tmp_path / "review.provenance.json"
    write_provenance_packet(record_path, receipt_paths, source_root, revision, ["src/app.py", "tests/test_app.py"], packet_path)
    verified = verify_provenance_packet(packet_path)
    assert verified["freshness"] == "unknown"
    assert verified["fresh"] is False
    assert verified["ok"] is False


def test_provenance_packet_is_portable_with_relocated_source_root(tmp_path: Path):
    source_root, record_path, receipt_paths, revision = _write_provenance_fixture(tmp_path)
    packet_path = tmp_path / "review.provenance.json"
    write_provenance_packet(record_path, receipt_paths, source_root, revision, ["src/app.py", "tests/test_app.py"], packet_path)
    relocated_root = tmp_path / "relocated" / "repo"
    relocated_root.parent.mkdir()
    (relocated_root / "src").mkdir(parents=True)
    (relocated_root / "tests").mkdir()
    for relative in ("src/app.py", "tests/test_app.py"):
        (relocated_root / relative).write_bytes((source_root / relative).read_bytes())
    relocated_packet = relocated_root.parent / "review.provenance.json"
    relocated_packet.write_bytes(packet_path.read_bytes())
    verified = verify_provenance_packet(relocated_packet, relocated_root)
    assert verified["ok"] is True
    assert verified["freshness"] == "matched"


def test_provenance_packet_rejects_receipt_binding_mismatch(tmp_path: Path):
    source_root, record_path, receipt_paths, revision = _write_provenance_fixture(tmp_path)
    payload = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    payload["detail"] = "different run"
    receipt_paths[0].write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        build_provenance_packet(record_path, receipt_paths, source_root, revision, ["src/app.py", "tests/test_app.py"])
    except ValueError as exc:
        assert "does not match task record" in str(exc) or "does not match" in str(exc)
    else:
        raise AssertionError("unbound evidence receipt was accepted")


def test_provenance_packet_rejects_symlink_source_and_preserves_output(tmp_path: Path):
    source_root, record_path, receipt_paths, revision = _write_provenance_fixture(tmp_path)
    link = source_root / "src" / "alias.py"
    link.symlink_to(source_root / "src" / "app.py")
    output = tmp_path / "review.provenance.json"
    output.write_text("existing\n", encoding="utf-8")
    try:
        write_provenance_packet(
            record_path,
            receipt_paths,
            source_root,
            revision,
            ["src/alias.py", "src/app.py", "tests/test_app.py"],
            output,
        )
    except ValueError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("symlink source was accepted")
    assert output.read_text(encoding="utf-8") == "existing\n"


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
