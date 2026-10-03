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
