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
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from benchmark_lab import run_benchmark  # noqa: E402


SCHEMA = "forgeyard-evaluation/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    return _digest(path.read_bytes())


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


def _refusal_coverage() -> dict[str, Any]:
    path = ROOT / "docs" / "workbench" / "fixtures" / "adversarial.json"
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"state": "blocked", "error": str(exc)}
    reports = payload.get("reports") if isinstance(payload, dict) else None
    if payload.get("schema") != "forgeyard-workbench-adversarial/v1" or not isinstance(reports, list):
        return {"state": "blocked", "error": "adversarial fixture schema or reports are invalid"}
    threats = [report.get("threat") for report in reports if isinstance(report, dict)]
    names = [report.get("name") for report in reports if isinstance(report, dict)]
    valid = (
        bool(reports)
        and len(threats) == len(reports)
        and all(isinstance(value, str) and value for value in threats)
        and len(set(threats)) == len(threats)
        and len(set(names)) == len(names)
        and all(report.get("ok") is False for report in reports if isinstance(report, dict))
    )
    return {
        "state": "pass" if valid else "blocked",
        "schema": payload.get("schema"),
        "reports": len(reports),
        "unique_threats": len(set(threats)),
        "mutation_operators": sorted(set(threats)),
        "fixture_sha256": _digest(raw),
    }


def _read_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 2 or not _SHA256.fullmatch(parts[0]):
            continue
        checksums[Path(parts[-1]).name] = parts[0]
    return checksums


def _artifact_observation(dist_dir: Path | None) -> dict[str, Any]:
    if dist_dir is None:
        return {"state": "unavailable", "reason": "dist_dir_not_provided"}
    if not dist_dir.is_dir():
        return {"state": "unavailable", "reason": "dist_dir_missing"}
    assets = sorted(path for path in dist_dir.iterdir() if path.is_file() and path.suffix in {".whl", ".gz"})
    sums_path = dist_dir / "SHA256SUMS"
    if not assets or not sums_path.is_file():
        return {"state": "unavailable", "reason": "wheel_sdist_or_checksums_missing"}
    checksums = _read_checksums(sums_path)
    mismatches: list[str] = []
    observations: list[dict[str, Any]] = []
    for path in assets:
        actual = _file_digest(path)
        expected = checksums.get(path.name)
        if expected != actual:
            mismatches.append(path.name)
        observations.append({"name": path.name, "bytes": path.stat().st_size, "sha256": actual})
    return {
        "state": "pass" if not mismatches and len(assets) >= 2 else "blocked",
        "assets": observations,
        "checksum_manifest_sha256": _file_digest(sums_path),
        "mismatches": mismatches,
    }


def _install_observation(dist_dir: Path | None, artifact: dict[str, Any], install: bool) -> dict[str, Any]:
    if not install:
        return {"state": "unavailable", "reason": "install_not_requested"}
    if artifact.get("state") != "pass":
        return {"state": "unavailable", "reason": "verified_artifacts_required"}
    wheel = next((item["name"] for item in artifact["assets"] if item["name"].endswith(".whl")), None)
    if not wheel or dist_dir is None:
        return {"state": "unavailable", "reason": "wheel_missing"}
    with tempfile.TemporaryDirectory(prefix="forgeyard-evaluation-install-") as directory:
        venv = Path(directory) / "venv"
        try:
            create = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True, text=True, check=False)
            if create.returncode != 0:
                return {"state": "blocked", "reason": "venv_creation_failed", "exit_code": create.returncode}
            python = venv / "bin" / "python"
            result = subprocess.run(
                [str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(dist_dir / wheel)],
                capture_output=True,
                text=True,
                check=False,
            )
            version = subprocess.run([str(venv / "bin" / "forgeyard"), "--version"], capture_output=True, text=True, check=False)
        except OSError as exc:
            return {"state": "blocked", "reason": str(exc)}
    return {
        "state": "pass" if result.returncode == 0 and version.returncode == 0 else "blocked",
        "install_exit_code": result.returncode,
        "version_exit_code": version.returncode,
        "version": version.stdout.strip()[:160] if version.returncode == 0 else None,
        "stdout_sha256": _digest(result.stdout.encode("utf-8")),
        "stderr_sha256": _digest(result.stderr.encode("utf-8")),
    }


def evaluate(iterations: int = 5, warmup: int = 1, dist_dir: Path | None = None, install: bool = False) -> dict[str, Any]:
    correctness, benchmark = _correctness(iterations, warmup)
    refusal = _refusal_coverage()
    artifact = _artifact_observation(dist_dir)
    install_result = _install_observation(dist_dir, artifact, install)
    observations = {
        "correctness": correctness,
        "refusal": refusal,
        "performance": {
            "state": "measured" if benchmark else "unavailable",
            "operations": benchmark.get("operations", {}) if benchmark else {},
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
        "result": "pass" if correctness.get("state") == "pass" and refusal.get("state") == "pass" else "blocked",
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
