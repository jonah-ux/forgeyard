#!/usr/bin/env python3
"""Run the reproducible Forgeyard evaluation suite.

The suite separates deterministic contract checks, adversarial refusal coverage,
machine-local measurements, and optional release-artifact/install observations.
Unavailable optional inputs remain explicit in the receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from benchmark_lab import run_benchmark  # noqa: E402
from audit_public_surface import _artifact_audit  # noqa: E402
from forgeyard.evaluation import is_passing_runtime_evaluation, run_refusal_evaluation  # noqa: E402


SCHEMA = "forgeyard-evaluation/v1"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None


def _correctness(iterations: int, warmup: int) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        benchmark = run_benchmark(iterations=iterations, warmup=warmup)
    except (OSError, ValueError, RuntimeError) as exc:
        return {"state": "blocked", "error": str(exc)}, {}
    return {
        "state": "pass" if benchmark.get("result") == "pass" and benchmark.get("guards", {}).get("packet_ok") else "blocked",
        "schema": benchmark.get("schema"),
        "operations": sorted(benchmark.get("operations", {})),
        "dataset": benchmark.get("dataset"),
        "guards": benchmark.get("guards"),
    }, benchmark


def _fixture_catalog() -> dict[str, Any]:
    path = ROOT / "docs" / "workbench" / "fixtures" / "adversarial.json"
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"state": "blocked", "error": str(exc)}
    reports = payload.get("reports") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("schema") != "forgeyard-workbench-adversarial/v1" or not isinstance(reports, list):
        return {"state": "blocked", "error": "adversarial fixture schema or reports are invalid"}
    threats = [report.get("threat") for report in reports if isinstance(report, dict)]
    names = [report.get("name") for report in reports if isinstance(report, dict)]
    valid = (
        bool(reports)
        and len(threats) == len(reports)
        and all(isinstance(value, str) and value for value in threats)
        and all(isinstance(value, str) and value for value in names)
        and len(set(threats)) == len(threats)
        and len(set(names)) == len(names)
        and all(report.get("ok") is False for report in reports if isinstance(report, dict))
    )
    return {
        "state": "pass" if valid else "blocked",
        "schema": payload.get("schema"),
        "reports": len(reports),
        "unique_threats": len(set(value for value in threats if isinstance(value, str))),
        "mutation_operators": sorted(set(value for value in threats if isinstance(value, str))),
        "fixture_sha256": _digest(raw),
    }


def _refusal_coverage() -> dict[str, Any]:
    catalog = _fixture_catalog()
    runtime = run_refusal_evaluation()
    if not isinstance(runtime, dict):
        runtime = {"result": "blocked", "cases": [], "reason": "invalid_runtime_receipt"}
    runtime_cases = runtime.get("cases")
    if not isinstance(runtime_cases, list):
        runtime_cases = []
    return {
        "state": "pass" if catalog["state"] == "pass" and is_passing_runtime_evaluation(runtime) else "blocked",
        "fixture_state": catalog["state"],
        "fixture_sha256": catalog.get("fixture_sha256"),
        "fixture_catalog": catalog,
        "runtime": runtime,
        # Retain v1 catalog fields; runtime evidence is explicit and separate.
        "schema": catalog.get("schema"),
        "reports": catalog.get("reports", 0),
        "unique_threats": catalog.get("unique_threats", 0),
        "mutation_operators": catalog.get("mutation_operators", []),
        "executed_operators": [case["name"] for case in runtime_cases
                               if isinstance(case, dict) and isinstance(case.get("name"), str)
                               and case["name"] != "positive-control"],
    }


def _artifact_observation(dist_dir: Path | None) -> dict[str, Any]:
    return _artifact_audit(dist_dir)


def _install_observation(dist_dir: Path | None, artifact: dict[str, Any], install: bool,
                         expected_runtime: dict[str, Any]) -> dict[str, Any]:
    if not install:
        return {"state": "unavailable", "reason": "install_not_requested"}
    if artifact.get("state") != "pass":
        return {"state": "unavailable", "reason": "verified_artifacts_required"}
    wheel = next((item["name"] for item in artifact["assets"] if item["name"].endswith(".whl")), None)
    if not wheel or dist_dir is None:
        return {"state": "unavailable", "reason": "wheel_missing"}
    wheel_path = (dist_dir / wheel).resolve()
    with tempfile.TemporaryDirectory(prefix="forgeyard-evaluation-install-") as directory:
        venv = Path(directory) / "venv"
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        try:
            started = time.perf_counter_ns()
            create = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True, text=True, check=False, timeout=60)
            venv_elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            if create.returncode != 0:
                return {"state": "blocked", "reason": "venv_creation_failed", "exit_code": create.returncode}
            python = venv / "bin" / "python"
            started = time.perf_counter_ns()
            result = subprocess.run(
                [str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel_path)],
                capture_output=True,
                text=True,
                check=False,
                cwd=directory,
                env=environment,
                timeout=90,
            )
            install_elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            if result.returncode != 0:
                return {"state": "blocked", "reason": "offline_install_failed", "exit_code": result.returncode}
            identity = subprocess.run(
                [str(python), "-I", "-c", "from pathlib import Path; import sys, forgeyard; assert Path(forgeyard.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())"],
                capture_output=True, text=True, check=False, cwd=directory, env=environment, timeout=15,
            )
            version = subprocess.run([str(venv / "bin" / "forgeyard"), "--version"], capture_output=True, text=True, check=False, cwd=directory, env=environment, timeout=15)
            runtime = subprocess.run([str(venv / "bin" / "forgeyard"), "evaluate-refusals"], capture_output=True, text=True, check=False, cwd=directory, env=environment, timeout=30)
            receipt = json.loads(runtime.stdout)
            runtime_ok = (
                is_passing_runtime_evaluation(receipt) and is_passing_runtime_evaluation(expected_runtime)
                and receipt["cases"] == expected_runtime.get("cases")
                and type(receipt.get("executed")) is int and receipt["executed"] == len(receipt["cases"])
                and all(receipt.get(key) == expected_runtime.get(key) for key in (
                    "package_version", "corpus_sha256", "implementation_sha256", "suite_sha256"))
                and version.stdout.strip() == expected_runtime.get("package_version")
            )
        except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired):
            return {"state": "blocked", "reason": "consumer_invocation_or_receipt_failed"}
    return {
        "state": "pass" if identity.returncode == 0 and version.returncode == 0 and runtime.returncode == 0 and runtime_ok else "blocked",
        "install_exit_code": result.returncode,
        "version_exit_code": version.returncode,
        "version": version.stdout.strip()[:160] if version.returncode == 0 else None,
        "stdout_sha256": _digest(result.stdout.encode("utf-8")),
        "stderr_sha256": _digest(result.stderr.encode("utf-8")),
        "installed_origin_verified": identity.returncode == 0,
        "runtime_exit_code": runtime.returncode,
        "runtime_evaluation": receipt if runtime_ok else None,
        "venv_elapsed_ms": round(venv_elapsed_ms, 3),
        "install_elapsed_ms": round(install_elapsed_ms, 3),
    }


def evaluate(iterations: int = 5, warmup: int = 1, dist_dir: Path | None = None, install: bool = False) -> dict[str, Any]:
    correctness, benchmark = _correctness(iterations, warmup)
    refusal = _refusal_coverage()
    artifact = _artifact_observation(dist_dir)
    install_result = _install_observation(dist_dir, artifact, install, refusal["runtime"])
    observations = {
        "correctness": correctness,
        "refusal": refusal,
        "performance": {
            "state": "measured" if benchmark else "unavailable",
            "operations": benchmark.get("operations", {}) if benchmark else {},
            "environment": benchmark.get("runtime", {}) if benchmark else {},
            "protocol": benchmark.get("measurement_protocol", {}) if benchmark else {},
            "iterations": benchmark.get("iterations") if benchmark else None,
            "warmup": benchmark.get("warmup") if benchmark else None,
        },
        "artifact": artifact,
        "install": install_result,
    }
    return {
        "schema": SCHEMA,
        "source": {"revision": _source_revision(), "python": platform.python_version()},
        "datasets": {
            "correctness": correctness.get("dataset"),
            "refusal": {"fixture": "forgeyard-workbench-adversarial/v1", "sha256": refusal.get("fixture_sha256")},
        },
        "observations": observations,
        "result": "pass" if (
            correctness.get("state") == "pass" and refusal.get("state") == "pass"
            and (dist_dir is None or artifact.get("state") == "pass")
            and (not install or install_result.get("state") == "pass")
        ) else "blocked",
        "limits": [
            "performance values are machine-local observations",
            "artifact and install observations are unavailable unless --dist-dir and --install are supplied",
            "fixtures are synthetic and do not measure provider, network, database, model, deployment, adoption, or production behavior",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--dist-dir", type=Path)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.iterations, args.warmup, args.dist_dir, args.install)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"schema": SCHEMA, "result": "blocked", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2 if args.json else None, sort_keys=True))
    return 0 if report["result"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
