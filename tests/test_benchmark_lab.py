import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "scripts" / "benchmark_lab.py"
    spec = importlib.util.spec_from_file_location("benchmark_lab", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lab_benchmark_has_fixed_dataset_and_bounded_operations():
    receipt = _module().run_benchmark(iterations=2, warmup=0)
    assert receipt["schema"] == "forgeyard-lab-benchmark/v1"
    assert receipt["result"] == "pass"
    assert receipt["dataset"]["reports"] == 9
    assert receipt["dataset"]["bytes"] > 0
    assert set(receipt["operations"]) == {"parse", "validate", "index", "replay", "compose", "packet_verify"}
    assert all(operation["samples"] == 2 for operation in receipt["operations"].values())
    assert all(operation["memory"]["state"] == "measured" and operation["memory"]["peak_python_bytes"] >= 0
               for operation in receipt["operations"].values())
    assert receipt["runtime"]["architecture"]
    assert receipt["measurement_protocol"]["operation_order"] == list(receipt["operations"])
    assert receipt["guards"] == {"reviewable": True, "packet_ok": True, "private_payloads_exported": False}


def test_memory_measurement_preserves_a_callers_tracing_session(monkeypatch):
    module = _module()
    monkeypatch.setattr(module.tracemalloc, "is_tracing", lambda: True)
    def forbidden():
        raise AssertionError("must not start or stop caller tracing")
    monkeypatch.setattr(module.tracemalloc, "start", forbidden)
    monkeypatch.setattr(module.tracemalloc, "stop", forbidden)
    result = module._measure(lambda: bytearray(4096), iterations=1, warmup=0)
    assert result["samples"] == 1
    assert result["memory"] == {"state": "unavailable", "reason": "caller_tracing_active"}
