import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "scripts" / "evaluate_lab.py"
    spec = importlib.util.spec_from_file_location("evaluate_lab", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evaluation_distinguishes_pass_measurement_and_unavailable_inputs():
    report = _module().evaluate(iterations=1, warmup=0)
    assert report["schema"] == "forgeyard-evaluation/v1"
    assert report["result"] == "pass"
    assert report["observations"]["correctness"]["state"] == "pass"
    assert report["observations"]["refusal"]["state"] == "pass"
    assert report["observations"]["performance"]["state"] == "measured"
    assert report["observations"]["artifact"]["state"] == "unavailable"
    assert report["observations"]["install"]["state"] == "unavailable"
    assert report["observations"]["refusal"]["unique_threats"] == 15
