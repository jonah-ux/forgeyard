#!/usr/bin/env python3
"""Measure Forgeyard's bounded local lab path on a fixed synthetic dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forgeyard.core import (  # noqa: E402
    Evidence,
    EvidenceStatus,
    TaskRecord,
    evidence_from_report,
    read_record,
    verify_provenance_packet,
    write_evidence_receipt,
    write_provenance_packet,
    write_record,
)


SCHEMA = "forgeyard-lab-benchmark/v1"
REVISION = "forgeyard-lab-benchmark-revision"


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.95))]


def _measure(operation: Callable[[], Any], iterations: int, warmup: int) -> dict[str, Any]:
    for _ in range(warmup):
        operation()
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        operation()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    memory: dict[str, Any] = {"state": "unavailable", "reason": "caller_tracing_active"}
    if not tracemalloc.is_tracing():
        tracemalloc.start()
        try:
            operation()
            _, peak = tracemalloc.get_traced_memory()
            memory = {"state": "measured", "peak_python_bytes": peak, "samples": 1}
        finally:
            tracemalloc.stop()
    return {
        "samples": len(samples),
        "median_ms": round(statistics.median(samples), 3),
        "p95_ms": round(_p95(samples), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
        "memory": memory,
    }


def _load_fixture() -> tuple[list[dict[str, Any]], list[bytes]]:
    fixture_path = ROOT / "docs" / "workbench" / "fixtures" / "specialists.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("schema") != "forgeyard-workbench-fixture/v1" or not fixture.get("reports"):
        raise ValueError("benchmark fixture must be a non-empty Workbench v1 fixture")
    reports = fixture["reports"]
    encoded = [json.dumps(report, sort_keys=True).encode("utf-8") for report in reports]
    return reports, encoded


def _build_packet_fixture(work: Path) -> tuple[Path, Path, Path, list[Path]]:
    source_root = work / "source"
    (source_root / "src").mkdir(parents=True)
    record_path = work / "record.json"
    packet_path = work / "packet.json"
    report_paths: list[Path] = []
    record = TaskRecord("benchmark-packet", "synthetic-fixture", "verify provenance packet")
    for name in ("context", "policy"):
        report_path = work / f"{name}.json"
        report_path.write_text(json.dumps({"schema": f"{name}/v1", "ok": True}) + "\n", encoding="utf-8")
        report_paths.append(report_path)
        evidence = evidence_from_report(report_path, name, REVISION)
        record.add_evidence(evidence)
        source_path = source_root / "src" / f"{name}.json"
        source_path.write_bytes(report_path.read_bytes())
    record.finalize()
    write_record(record, record_path)
    receipt_paths = [work / "context.receipt.json", work / "policy.receipt.json"]
    for name, receipt_path in zip(("context", "policy"), receipt_paths):
        write_evidence_receipt(record_path, name, [f"src/{name}.json"], receipt_path)
    write_provenance_packet(record_path, receipt_paths, source_root, REVISION, ["src/context.json", "src/policy.json"], packet_path)
    return record_path, packet_path, source_root, report_paths


def run_benchmark(iterations: int = 20, warmup: int = 3) -> dict[str, Any]:
    if iterations < 1 or iterations > 200:
        raise ValueError("iterations must be between 1 and 200")
    if warmup < 0 or warmup > 50:
        raise ValueError("warmup must be between 0 and 50")
    reports, encoded = _load_fixture()
    with tempfile.TemporaryDirectory(prefix="forgeyard-lab-benchmark-") as directory:
        work = Path(directory)
        report_paths = []
        for index, report in enumerate(reports):
            path = work / f"report-{index}.json"
            path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
            report_paths.append(path)
        record_path, packet_path, source_root, _ = _build_packet_fixture(work)
        parsed: list[dict[str, Any]] = []
        validated: list[Evidence] = []
        index: dict[str, dict[str, Any]] = {}

        def parse() -> None:
            parsed.clear()
            parsed.extend(json.loads(raw.decode("utf-8")) for raw in encoded)

        def validate() -> None:
            validated.clear()
            validated.extend(evidence_from_report(path, f"report-{number}", REVISION) for number, path in enumerate(report_paths))

        def build_index() -> None:
            index.clear()
            index.update({report["name"]: report for report in parsed})

        def replay() -> None:
            read_record(record_path)

        def compose() -> None:
            record = TaskRecord("benchmark-compose", "synthetic-fixture", "compose benchmark record")
            for number, evidence in enumerate(validated):
                record.add_evidence(Evidence(f"report-{number}", evidence.status, evidence.detail, REVISION))
            record.finalize()
            if not record.ready_for_review():
                raise RuntimeError("benchmark composition did not remain reviewable")

        def verify_packet() -> None:
            result = verify_provenance_packet(packet_path, source_root)
            if not result["ok"]:
                raise RuntimeError(f"benchmark packet verification failed: {result}")

        parse()
        validate()
        build_index()
        operations = {
            "parse": parse,
            "validate": validate,
            "index": build_index,
            "replay": replay,
            "compose": compose,
            "packet_verify": verify_packet,
        }
        measurements = {name: _measure(operation, iterations, warmup) for name, operation in operations.items()}

    dataset_bytes = sum(len(raw) for raw in encoded)
    return {
        "schema": SCHEMA,
        "dataset": {
            "fixture": "forgeyard-workbench-fixture/v1",
            "reports": len(reports),
            "bytes": dataset_bytes,
            "sha256": hashlib.sha256(b"".join(encoded)).hexdigest(),
        },
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "architecture": platform.machine(), "logical_cpus": os.cpu_count()},
        "measurement_protocol": {"latency": "perf_counter_ns/elapsed-ms",
                                 "memory": "separate-single-tracemalloc-peak-python-bytes",
                                 "operation_order": list(operations)},
        "iterations": iterations,
        "warmup": warmup,
        "operations": measurements,
        "guards": {"reviewable": True, "packet_ok": True, "private_payloads_exported": False},
        "result": "pass",
        "limits": [
            "timings are machine-local observations, not cross-machine rankings",
            "memory is a separate Python allocation peak, not process RSS or native allocation accounting",
            "memory is unavailable when the caller already owns an active tracing session",
            "the dataset is synthetic and does not measure provider, network, database, or model latency",
            "a passing benchmark does not claim deployment, adoption, or production readiness",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="pretty-print the JSON receipt")
    args = parser.parse_args(argv)
    try:
        receipt = run_benchmark(args.iterations, args.warmup)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"schema": SCHEMA, "result": "invalid", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(receipt, indent=2 if args.json else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
