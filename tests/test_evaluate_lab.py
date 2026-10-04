import importlib.util
import hashlib
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
    assert report["observations"]["performance"]["environment"]["architecture"]
    assert report["observations"]["performance"]["protocol"]["memory"] == "separate-single-tracemalloc-peak-python-bytes"
    assert report["observations"]["artifact"]["state"] == "unavailable"
    assert report["observations"]["install"]["state"] == "unavailable"
    assert report["observations"]["refusal"]["unique_threats"] == 15
    assert report["observations"]["refusal"]["runtime"]["result"] == "pass"


def test_explicit_checksum_mismatch_blocks_overall_result(tmp_path):
    for name in ("forgeyard-0.5.1-py3-none-any.whl", "forgeyard-0.5.1.tar.gz"):
        (tmp_path / name).write_bytes(b"synthetic artifact")
    (tmp_path / "SHA256SUMS").write_text("\n".join("0" * 64 + "  " + path.name for path in tmp_path.iterdir()) + "\n")
    report = _module().evaluate(iterations=1, warmup=0, dist_dir=tmp_path)
    assert report["observations"]["artifact"]["state"] == "blocked"
    assert report["result"] == "blocked"


def test_requested_install_failure_and_missing_inputs_block_result(monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "_artifact_observation", lambda path: {"state": "pass"})
    monkeypatch.setattr(module, "_install_observation", lambda *args: {"state": "blocked", "reason": "fixture_install_failure"})
    assert module.evaluate(iterations=1, warmup=0, dist_dir=Path("fixture"), install=True)["result"] == "blocked"
    assert _module().evaluate(iterations=1, warmup=0, install=True)["result"] == "blocked"


def test_runtime_failure_cannot_be_hidden_by_passing_fixture_catalog(monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "run_refusal_evaluation", lambda: {"result": "blocked", "cases": []})
    report = module.evaluate(iterations=1, warmup=0)
    assert report["observations"]["refusal"]["fixture_state"] == "pass"
    assert report["result"] == "blocked"


def test_empty_runtime_success_label_cannot_pass_source_evaluation(monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "run_refusal_evaluation", lambda: {"result": "pass", "cases": []})
    assert module.evaluate(iterations=1, warmup=0)["result"] == "blocked"


def test_artifact_checks_refuse_incomplete_and_symlinked_sets(tmp_path):
    module = _module()
    wheel = tmp_path / "forgeyard-0.5.1-py3-none-any.whl"
    wheel.write_bytes(b"synthetic artifact")
    (tmp_path / "SHA256SUMS").write_text(hashlib.sha256(wheel.read_bytes()).hexdigest() + "  " + wheel.name + "\n")
    assert module._artifact_observation(tmp_path)["state"] == "blocked"
    archive = tmp_path / "forgeyard-0.5.1.tar.gz"
    archive.symlink_to(wheel)
    assert module._artifact_observation(tmp_path)["state"] == "blocked"
