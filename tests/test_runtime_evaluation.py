import json
import pytest

from forgeyard import core, evaluation, interop
from forgeyard.cli import main


def test_native_suite_executes_and_has_a_positive_control():
    report = evaluation.run_refusal_evaluation()
    assert report["result"] == "pass"
    assert report["executed"] == len(report["cases"]) > 1
    assert report["cases"][0]["name"] == "positive-control"
    assert report["cases"][0]["observed"] == "admitted"
    assert all(case["executed"] is True and case["ok"] is True for case in report["cases"])
    assert len({case["name"] for case in report["cases"]}) == len(report["cases"])
    encoded = json.dumps(report)
    assert "synthetic-payload-marker" not in encoded
    assert "forgeyard-evaluation-" not in encoded


def test_suite_detects_a_verifier_that_accepts_stale_and_tampered_packets(monkeypatch):
    monkeypatch.setattr(core, "verify_provenance_packet", lambda *args: {"ok": True, "fresh": True, "freshness": "matched"})
    report = evaluation.run_refusal_evaluation()
    assert report["result"] == "blocked"
    cases = {case["name"]: case for case in report["cases"]}
    assert cases["positive-control"]["ok"] is True
    assert cases["stale-source"]["ok"] is False
    assert cases["packet-digest-tamper"]["ok"] is False
    assert cases["unbound-source"]["ok"] is False


def test_unexpected_exceptions_are_failures_and_do_not_echo_messages(monkeypatch):
    def broken(*args):
        raise RuntimeError("synthetic-sensitive-marker")
    monkeypatch.setattr(core, "verify_provenance_packet", broken)
    report = evaluation.run_refusal_evaluation()
    assert report["result"] == "blocked"
    assert any(case["observed"] == "unexpected_exception" for case in report["cases"])
    assert "synthetic-sensitive-marker" not in json.dumps(report)


def test_suite_rejects_a_verifier_that_refuses_every_packet(monkeypatch):
    monkeypatch.setattr(core, "verify_provenance_packet", lambda *args: {"ok": False, "fresh": False, "freshness": "unknown"})
    report = evaluation.run_refusal_evaluation()
    assert report["result"] == "blocked"
    assert report["cases"][0]["name"] == "positive-control"
    assert report["cases"][0]["ok"] is False


def test_an_unrelated_refusal_does_not_pass_a_negative_case(monkeypatch):
    validate = interop.validate_evidence
    def refuse(document):
        if isinstance(document, dict) and document.get("schema") == "ai-work-evidence/v99":
            raise ValueError("unrelated refusal")
        return validate(document)
    monkeypatch.setattr(interop, "validate_evidence", refuse)
    report = evaluation.run_refusal_evaluation()
    assert report["result"] == "blocked"
    cases = {case["name"]: case for case in report["cases"]}
    assert cases["schema-drift"]["observed"] == "wrong_refusal"
    assert cases["schema-drift"]["ok"] is False


def test_native_cli_emits_one_report(capsys):
    assert main(["evaluate-refusals"]) == 0
    assert json.loads(capsys.readouterr().out)["result"] == "pass"


@pytest.mark.parametrize("original_status,replacement", [
    (core.EvidenceStatus.PASS, core.EvidenceStatus.UNKNOWN),
    (core.EvidenceStatus.FAIL, core.EvidenceStatus.PASS),
])
def test_projection_control_detects_changed_pass_and_fail_status(monkeypatch, original_status, replacement):
    project = core.evidence_from_report
    def changed(*args, **kwargs):
        evidence = project(*args, **kwargs)
        if evidence.detail.startswith("schema=fixture/v1;") and evidence.status is original_status:
            return core.Evidence(evidence.name, replacement, evidence.detail, evidence.revision)
        return evidence
    monkeypatch.setattr(core, "evidence_from_report", changed)
    report = evaluation.run_refusal_evaluation()
    assert report["result"] == "blocked"
    case = next(case for case in report["cases"] if case["name"] == "payload-redaction")
    assert case["observed"] == "projection_mismatch"


@pytest.mark.parametrize("limit", [0, 1, 18])
def test_empty_or_truncated_corpus_blocks_the_native_suite_and_cli(monkeypatch, capsys, limit):
    cases = evaluation._cases()
    monkeypatch.setattr(evaluation, "_cases", lambda: cases[:limit])
    report = evaluation.run_refusal_evaluation()
    assert report["result"] == "blocked"
    assert evaluation.is_passing_runtime_evaluation(report) is False
    assert main(["evaluate-refusals"]) == 2
    assert json.loads(capsys.readouterr().out)["result"] == "blocked"
