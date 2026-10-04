"""Bind the public owner declaration to real Forgeyard producer output."""

import json
from pathlib import Path

from forgeyard.cli import main
from forgeyard.interop import build_evidence, write_evidence


ROOT = Path(__file__).resolve().parents[1]


def owner_declaration():
    return json.loads((ROOT / "conformance/agent-systems-lab.json").read_text(encoding="utf-8"))


def test_declared_protocols_are_emitted_by_native_producers(tmp_path, capsys):
    declaration = owner_declaration()
    assert declaration["schema"] == "forgeyard-lab-conformance/v1"
    assert declaration["owner"] == "forgeyard"
    assert declaration["repository"] == "https://github.com/jonah-ux/forgeyard"
    for field in ("native_schemas", "capabilities"):
        assert declaration[field] == sorted(set(declaration[field]))
    for protocols in declaration["capability_protocols"].values():
        assert protocols == sorted(set(protocols))
    source = tmp_path / "source"
    source.mkdir()
    report_path = source / "evidence.json"
    evidence = build_evidence(
        evidence_id="lab:fixture", source="forgeyard", source_version="fixture",
        created_at="2026-01-01T00:00:00Z", subject="Synthetic compatibility",
        summary="Synthetic producer control", status="observed",
    )
    write_evidence(evidence, report_path)
    observed = {"work.evidence": {evidence["schema"]}}

    def invoke(arguments):
        assert main(arguments) == 0
        return json.loads(capsys.readouterr().out)

    record = tmp_path / "record.json"
    compose = invoke([
        "compose", "--task-id", "lab-fixture", "--repository", "synthetic",
        "--request", "Review synthetic evidence", "--revision", "fixture-revision",
        "--input", f"check={report_path}", "--output", str(record),
    ])
    review = invoke(["review", str(record), "--revision", "fixture-revision", "--path", "evidence.json"])
    observed["review.compose"] = {compose["schema"], review["schema"]}
    assert compose["status"] == "ready_for_review"
    assert review["reviewable"] is True
    verification = invoke(["verify", str(record), "--sha256", compose["sha256"]])
    observed["review.verify"] = {verification["schema"]}
    assert verification["reviewable"] is True

    receipt = tmp_path / "receipt.json"
    invoke(["receipt", str(record), "--name", "check", "--path", "evidence.json", "--output", str(receipt)])
    packet = tmp_path / "packet.json"
    invoke([
        "packet", str(record), "--receipt", str(receipt), "--source-root", str(source),
        "--revision", "fixture-revision", "--path", "evidence.json", "--output", str(packet),
    ])
    packet_verification = invoke(["verify-packet", str(packet), "--source-root", str(source)])
    assert packet_verification["ok"] is True
    assert packet_verification["fresh"] is True
    observed["provenance.packet"] = {
        json.loads(receipt.read_text(encoding="utf-8"))["schema"],
        json.loads(packet.read_text(encoding="utf-8"))["schema"],
        packet_verification["schema"],
    }
    evaluation = invoke(declaration["evaluation"]["command"][1:])
    observed["evaluation.refusals"] = {evaluation["schema"]}
    assert evaluation["result"] == "pass"

    assert set(declaration["capabilities"]) == set(observed)
    assert {key: set(value) for key, value in declaration["capability_protocols"].items()} == observed
    assert set(declaration["native_schemas"]) == set().union(*observed.values())


def test_declared_refusals_run_against_the_native_implementation(capsys):
    declaration = owner_declaration()
    assert main(declaration["evaluation"]["command"][1:]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == declaration["evaluation"]["schema"]
    assert report["executed"] == declaration["evaluation"]["case_count"]
    assert report["corpus_sha256"] == declaration["evaluation"]["corpus_sha256"]
    cases = {case["name"]: case for case in report["cases"]}
    for name in declaration["negative_cases"]:
        case = cases[name]
        assert case["executed"] is True
        assert case["ok"] is True
        assert case["expected"] in {"refused", "blocked", "unbound"}
        assert case["observed"] == case["expected"]
