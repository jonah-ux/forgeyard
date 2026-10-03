import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "scripts" / "run_reference_flow.py"
    spec = importlib.util.spec_from_file_location("run_reference_flow", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_flow_preserves_success_and_refusal_outcomes():
    module = _module()
    for scenario, outcome in (("passing", "reviewable"), ("blocked", "blocked"), ("tampered", "refused")):
        payload = module.run_flow(scenario)
        assert payload["schema"] == "forgeyard-reference-flow/v1"
        assert payload["scenario"] == scenario
        assert payload["result"] == "pass"
        assert payload["outcome"] == outcome
        assert len(payload["stages"]) == 6


def test_installed_flow_requires_owner_artifacts_and_preserves_command_boundaries(tmp_path):
    module = _module()
    assert module._command('"/tmp/tool with spaces" --flag') == ["/tmp/tool with spaces", "--flag"]
    try:
        module._installed_flow(
            "passing",
            chatlens_trace=tmp_path / "missing-trace.jsonl",
            atlas_state=tmp_path / "missing-state.jsonl",
            command_map={
                "chatlens": "chatlens",
                "atlas": "atlas",
                "agent_proof": "agent-proof",
                "forgeyard": "forgeyard",
            },
        )
    except module.InstalledFlowUnavailable as exc:
        assert "requires readable ChatLens trace and Atlas state" in str(exc)
    else:
        raise AssertionError("installed flow must not substitute fixtures for missing owner artifacts")
