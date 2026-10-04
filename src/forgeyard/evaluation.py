"""Deterministic, offline checks of Forgeyard's native admission boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import tempfile
from typing import Callable

from . import __version__, core, interop


SCHEMA = "forgeyard-runtime-evaluation/v1"
REVISION = "synthetic-revision"
# The reviewed v1 corpus must not silently shrink or change admission semantics.
CORPUS_SHA256 = "5f70a79f2be8dc48ec26ec4f569951e342ea7717997b11084104cbfc63e0733e"
CASE_COUNT = 19


@dataclass(frozen=True)
class Case:
    name: str
    expected: str
    boundary: str
    action: Callable[[Path], str]


def _record(status=core.EvidenceStatus.PASS):
    record = core.TaskRecord("evaluation", "synthetic-repo", "Synthetic contract evaluation")
    record.add_evidence(core.Evidence("check", status, "Synthetic result", REVISION))
    record.finalize()
    return record


def _shared():
    return interop.build_evidence(
        evidence_id="evaluation:fixture", source="atlas", source_version="fixture",
        created_at="2026-01-01T00:00:00Z", subject="Synthetic", summary="Fixture",
        status="observed",
    )


def _refusal(operation, reason):
    try:
        operation()
    except ValueError as exc:
        # Match the owning layer's reason; an unrelated refusal is a failed check.
        return "refused" if reason in str(exc) else "wrong_refusal"
    return "accepted"


def _mutate_shared(field, value, reason):
    def run(root):
        document = _shared()
        document[field] = value
        return _refusal(lambda: interop.validate_evidence(document), reason)
    return run


def _packet_fixture(root):
    source_root = root / "source"
    source_root.mkdir()
    (source_root / "fixture.txt").write_text("synthetic source\n", encoding="utf-8")
    record_path = root / "record.json"
    core.write_record(_record(), record_path)
    receipt_path = root / "receipt.json"
    core.write_evidence_receipt(record_path, "check", ["fixture.txt"], receipt_path)
    packet_path = root / "packet.json"
    core.write_provenance_packet(record_path, [receipt_path], source_root, REVISION,
                                 ["fixture.txt"], packet_path)
    return source_root, record_path, receipt_path, packet_path


def _positive(root):
    source_root, record_path, _, packet_path = _packet_fixture(root)
    record = core.verify_record(record_path)
    packet = core.verify_provenance_packet(packet_path, source_root)
    interop.validate_evidence(_shared())
    return "admitted" if record["reviewable"] is True and packet["ok"] is True else "blocked"


def _duplicate(root):
    record = _record()
    return _refusal(lambda: record.add_evidence(record.evidence[0]), "duplicate evidence name")


def _nonpassing(root):
    for status in (core.EvidenceStatus.FAIL, core.EvidenceStatus.UNKNOWN, core.EvidenceStatus.SKIPPED):
        record = _record(status)
        if record.status != core.TaskStatus.BLOCKED or record.ready_for_review():
            return "admitted"
        if _refusal(lambda: core.build_review_packet(record, REVISION, ["fixture.txt"]),
                    "passing evidence") != "refused":
            return "wrong_refusal"
    return "blocked"


def _unknown_projection(root):
    document = _shared()
    document["status"] = "unknown"
    source = root / "shared.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    evidence = core.evidence_from_report(source, "check", REVISION)
    record = core.TaskRecord("evaluation", "synthetic", "Synthetic projection")
    record.add_evidence(evidence)
    record.finalize()
    return "blocked" if evidence.status is core.EvidenceStatus.UNKNOWN and not record.ready_for_review() else "admitted"


def _false_completion(root):
    document = _record(core.EvidenceStatus.UNKNOWN).as_dict()
    document["status"] = "complete"
    path = root / "false-completion.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return _refusal(lambda: core.read_record(path), "contradicts evidence")


def _redaction(root):
    marker = "synthetic-payload-marker"
    source = root / "report.json"
    for ok, status in ((True, core.EvidenceStatus.PASS), (False, core.EvidenceStatus.FAIL)):
        source.write_text(json.dumps({"schema": "fixture/v1", "ok": ok,
                                      "details": marker, "output": marker}), encoding="utf-8")
        evidence = core.evidence_from_report(source, "check", REVISION)
        if marker in json.dumps(evidence.as_dict()):
            return "leaked"
        if (evidence.status is not status or evidence.name != "check" or evidence.revision != REVISION
                or evidence.detail != f"schema=fixture/v1; ok={str(ok).lower()}"):
            return "projection_mismatch"
    return "redacted"


def _malformed_report(root):
    source = root / "report.json"
    source.write_text("[1,2,3]", encoding="utf-8")
    return _refusal(lambda: core.evidence_from_report(source, "check"), "boolean ok")


def _record_tamper(root):
    path = root / "record.json"
    digest = core.write_record(_record(), path)
    document = json.loads(path.read_text())
    document["request"] = "changed synthetic request"
    path.write_text(json.dumps(document), encoding="utf-8")
    return _refusal(lambda: core.verify_record(path, digest), "digest mismatch")


def _stale_source(root):
    source_root, _, _, packet = _packet_fixture(root)
    (source_root / "fixture.txt").write_text("changed synthetic source\n", encoding="utf-8")
    result = core.verify_provenance_packet(packet, source_root)
    return "refused" if result["ok"] is False and result["fresh"] is False else "accepted"


def _packet_tamper(root):
    source_root, _, _, packet = _packet_fixture(root)
    document = json.loads(packet.read_text())
    document["revision"] = "changed-revision"
    packet.write_text(json.dumps(document), encoding="utf-8")
    result = core.verify_provenance_packet(packet, source_root)
    return "refused" if result["ok"] is False else "accepted"


def _unbound_packet(root):
    _, _, _, packet = _packet_fixture(root)
    result = core.verify_provenance_packet(packet)
    return "unbound" if result["ok"] is False and result["freshness"] == "unknown" else "accepted"


def _symlink(root):
    source_root, record, receipt, _ = _packet_fixture(root)
    (root / "outside.txt").write_text("synthetic outside\n", encoding="utf-8")
    (source_root / "fixture.txt").unlink()
    (source_root / "fixture.txt").symlink_to(root / "outside.txt")
    return _refusal(lambda: core.build_provenance_packet(record, [receipt], source_root,
                                                        REVISION, ["fixture.txt"]), "symlink")


def _duplicate_receipt(root):
    source_root, record, receipt, _ = _packet_fixture(root)
    return _refusal(lambda: core.build_provenance_packet(record, [receipt, receipt], source_root,
                                                        REVISION, ["fixture.txt"]), "duplicate")


def _cases():
    return (
        Case("positive-control", "admitted", "record+interop+live-provenance", _positive),
        Case("duplicate-delivery", "refused", "record.add_evidence", _duplicate),
        Case("schema-drift", "refused", "interop.validate_evidence",
             _mutate_shared("schema", "ai-work-evidence/v99", "unsupported")),
        Case("unbounded-summary", "refused", "interop.validate_evidence",
             _mutate_shared("summary", "x" * 2049, "bounded")),
        Case("raw-field-injection", "refused", "interop.validate_evidence",
             _mutate_shared("raw_prompt", "synthetic marker", "unknown fields")),
        Case("malformed-root", "refused", "interop.validate_evidence",
             lambda root: _refusal(lambda: interop.validate_evidence([]), "JSON object")),
        Case("unknown-projection", "blocked", "evidence_from_report+finalize", _unknown_projection),
        Case("nonpassing-evidence", "blocked", "record.finalize+review", _nonpassing),
        Case("false-completion", "refused", "record.read", _false_completion),
        Case("payload-redaction", "redacted", "evidence_from_report", _redaction),
        Case("malformed-report", "refused", "evidence_from_report", _malformed_report),
        Case("revision-mismatch", "refused", "review.build",
             lambda root: _refusal(lambda: core.build_review_packet(_record(), "other", ["fixture.txt"]), "revision")),
        Case("path-traversal", "refused", "review.build",
             lambda root: _refusal(lambda: core.build_review_packet(_record(), REVISION, ["../outside.txt"]), "repository-relative")),
        Case("record-digest-tamper", "refused", "record.verify", _record_tamper),
        Case("stale-source", "refused", "provenance.verify-live-source", _stale_source),
        Case("packet-digest-tamper", "refused", "provenance.verify", _packet_tamper),
        Case("unbound-source", "unbound", "provenance.verify", _unbound_packet),
        Case("symlink-escape", "refused", "provenance.build", _symlink),
        Case("duplicate-receipt", "refused", "provenance.build", _duplicate_receipt),
    )


def is_passing_runtime_evaluation(report):
    """Require the complete reviewed corpus, not a caller's success label."""
    if not isinstance(report, dict) or report.get("schema") != SCHEMA or report.get("result") != "pass":
        return False
    if any(not isinstance(report.get(key), str) or not 1 <= len(report[key]) <= 64
           for key in ("package_version", "python")):
        return False
    implementation = report.get("implementation_sha256")
    if (not core._is_sha256(report.get("suite_sha256")) or not isinstance(implementation, dict)
            or set(implementation) != {"core", "interop"}
            or not all(core._is_sha256(value) for value in implementation.values())):
        return False
    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != CASE_COUNT or type(report.get("executed")) is not int or report["executed"] != CASE_COUNT:
        return False
    specifications = []
    for case in cases:
        if (not isinstance(case, dict) or case.get("executed") is not True or case.get("ok") is not True
                or "error_type" not in case or case["error_type"] is not None):
            return False
        if any(not isinstance(case.get(key), str) for key in ("name", "expected", "observed", "boundary")) or case["observed"] != case["expected"]:
            return False
        specifications.append({key: case[key] for key in ("name", "expected", "boundary")})
    encoded = json.dumps(specifications, sort_keys=True, separators=(",", ":")).encode()
    return report.get("corpus_sha256") == CORPUS_SHA256 and hashlib.sha256(encoded).hexdigest() == CORPUS_SHA256


def run_refusal_evaluation():
    """Execute every named case against the installed native implementation."""
    cases = _cases()
    specifications = [{"name": case.name, "expected": case.expected, "boundary": case.boundary}
                      for case in cases]
    encoded = json.dumps(specifications, sort_keys=True, separators=(",", ":")).encode()
    results = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="forgeyard-evaluation-") as directory:
            try:
                observed = case.action(Path(directory))
                error_type = None
            except Exception as exc:
                observed, error_type = "unexpected_exception", type(exc).__name__
        results.append({"name": case.name, "boundary": case.boundary, "expected": case.expected,
                        "observed": observed, "executed": True, "ok": observed == case.expected,
                        "error_type": error_type})
    return {
        "schema": SCHEMA,
        "result": "pass" if (
            len(results) == CASE_COUNT and hashlib.sha256(encoded).hexdigest() == CORPUS_SHA256
            and all(case["ok"] for case in results)
        ) else "blocked",
        "package_version": __version__, "python": platform.python_version(),
        "corpus_sha256": hashlib.sha256(encoded).hexdigest(),
        "implementation_sha256": {name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                                  for name, module in (("core", core), ("interop", interop))},
        "suite_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": results, "executed": len(results),
        "limits": ["synthetic, offline native Forgeyard cases only",
                   "does not execute specialist policy, sandbox, provider, deployment, or adoption behavior",
                   "corpus digest identifies case specifications; implementation digests identify native code"],
    }
