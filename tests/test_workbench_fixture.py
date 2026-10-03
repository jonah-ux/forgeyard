import json
from pathlib import Path


def test_workbench_fixture_covers_the_agent_systems_lab_layers():
    path = Path(__file__).parents[1] / "docs" / "workbench" / "fixtures" / "specialists.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    assert fixture["schema"] == "forgeyard-workbench-fixture/v1"
    reports = {report["name"]: report for report in fixture["reports"]}
    expected = {
        "mcp-doctor",
        "agent-proof",
        "context-integrity",
        "chatlens-trace",
        "atlas-receipt",
        "agent-policy",
        "agent-sandbox",
        "agent-resume",
        "agent-trace",
    }
    assert set(reports) == expected
    assert all(report["ok"] is True and report["details"] for report in reports.values())


def test_adversarial_fixture_is_explicitly_refusal_oriented():
    path = Path(__file__).parents[1] / "docs" / "workbench" / "fixtures" / "adversarial.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    assert fixture["schema"] == "forgeyard-workbench-adversarial/v1"
    assert fixture["scenario"] == "adversarial"
    assert len(fixture["reports"]) == 15
    assert all(report["ok"] is False and report["details"] and report["threat"] for report in fixture["reports"])
    assert {
        report["threat"] for report in fixture["reports"]
    } == {
        "stale-source",
        "capability-denial",
        "unenforced-execution",
        "partial-input",
        "unknown-lifecycle",
        "tampered-bytes",
        "path-traversal",
        "symlink-escape",
        "prompt-secret-leakage",
        "schema-drift",
        "duplicate-delivery",
        "stale-source-identity",
        "malformed-input",
        "unbounded-output",
        "false-completion",
    }
