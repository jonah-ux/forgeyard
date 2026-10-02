#!/usr/bin/env python3
"""Emit a deterministic-shape benchmark for the public Forgeyard CLI path."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time


def run(command: list[str], environment: dict[str, str]) -> tuple[float, dict]:
    started = time.perf_counter()
    result = subprocess.run(command, check=True, capture_output=True, text=True, env=environment)
    elapsed = (time.perf_counter() - started) * 1000
    return elapsed, json.loads(result.stdout)


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[min(len(values) - 1, int((len(values) - 1) * fraction))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.iterations < 1 or args.iterations > 200:
        parser.error("iterations must be between 1 and 200")
    root_source = Path(__file__).resolve().parents[1] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root_source) + os.pathsep + environment.get("PYTHONPATH", "")
    with tempfile.TemporaryDirectory(prefix="forgeyard-benchmark-") as directory:
        root = Path(directory)
        report = root / "report.json"
        record = root / "record.json"
        report.write_text(json.dumps({"schema": "mcp-doctor/v1", "ok": True}) + "\n", encoding="utf-8")
        compose_times: list[float] = []
        verify_times: list[float] = []
        for _ in range(args.iterations):
            compose_ms, composed = run([
                sys.executable, "-m", "forgeyard.cli", "compose",
                "--task-id", "benchmark", "--repository", "fixture",
                "--request", "benchmark compose", "--input", f"contract={report}",
                "--output", str(record),
            ], environment)
            verify_ms, verified = run([sys.executable, "-m", "forgeyard.cli", "verify", str(record)], environment)
            if composed.get("status") != "ready_for_review" or not verified.get("reviewable"):
                raise RuntimeError("benchmark command did not produce a reviewable record")
            compose_times.append(compose_ms)
            verify_times.append(verify_ms)
    receipt = {
        "schema": "forgeyard-benchmark/v1",
        "operation": "compose-and-verify",
        "iterations": args.iterations,
        "runtime": platform.python_version(),
        "compose_ms": {"median": round(statistics.median(compose_times), 3), "p95": round(percentile(compose_times, .95), 3)},
        "verify_ms": {"median": round(statistics.median(verify_times), 3), "p95": round(percentile(verify_times, .95), 3)},
        "result": "pass",
    }
    print(json.dumps(receipt, indent=2 if args.json else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
