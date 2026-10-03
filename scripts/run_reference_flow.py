#!/usr/bin/env python3
"""Run the offline Agent Systems Lab reference flow through Forgeyard's CLI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


REVISION = "agent-systems-lab-fixture-revision"
FLOW_SCHEMA = "forgeyard-reference-flow/v1"


def _report_payloads(scenario: str) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {
        "context": {
            "schema": "context-integrity/v1",
            "ok": True,
            "scope": "synthetic-context",
            "freshness": "current",
            "private_text": "omitted",
        },
        "policy": {
            "schema": "agent-policy/v1",
            "ok": True,
            "decision": "allow",
            "capability": "bounded-review",
        },
        "sandbox": {
            "schema": "agent-sandbox/v2",
            "ok": True,
            "backend": "fixture",
            "enforced": True,
        },
        "atlas": {
            "schema": "atlas-receipt/v1",
            "ok": True,
            "status": "completed",
            "approval": "observed",
        },
        "proof": {
            "schema": "agent-proof/interop/v1",
            "projection": {
                "status": {"ok": True, "state": "verified"},
                "source": {"schema": "agent-proof/v1", "revision": REVISION},
            },
        },
        "resume": {
            "schema": "agent-resume/v1",
            "ok": True,
            "checkpoint": "fixture-checkpoint",
            "continuation": "available",
        },
    }
    if scenario == "blocked":
        reports["atlas"] = {
            "schema": "ai-work-evidence/v1",
            "status": "unknown",
            "evidence_id": "atlas-fixture:unknown",
            "provenance": {"fixture": "agent-systems-lab"},
        }
    return reports


def _run_cli(root: Path, environment: dict[str, str], *arguments: str) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, "-m", "forgeyard.cli", *arguments],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Forgeyard CLI emitted non-JSON output: {result.stdout!r}") from exc
    return result.returncode, payload


def run_flow(scenario: str) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src") + os.pathsep + environment.get("PYTHONPATH", "")
    payloads = _report_payloads(scenario)
    with tempfile.TemporaryDirectory(prefix="forgeyard-reference-flow-") as directory:
        work = Path(directory)
        report_paths: dict[str, Path] = {}
        for name, payload in payloads.items():
            path = work / f"{name}.json"
            path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
            report_paths[name] = path

        record_path = work / "record.json"
        compose_args = [
            "compose",
            "--task-id",
            f"reference-flow-{scenario}",
            "--repository",
            "agent-systems-lab-fixture",
            "--request",
            "admit bounded agent work",
            "--revision",
            REVISION,
            "--output",
            str(record_path),
        ]
        for name in payloads:
            compose_args.extend(["--input", f"{name}={report_paths[name]}"])
        compose_exit, composed = _run_cli(root, environment, *compose_args)
        compose_status = composed.get("status")
        if scenario in {"passing", "tampered"}:
            if compose_exit != 0 or compose_status != "ready_for_review":
                raise RuntimeError(f"passing reference flow did not compose: {composed}")
        elif compose_exit != 2 or compose_status != "blocked":
            raise RuntimeError(f"blocked reference flow did not fail closed: {composed}")

        compose_digest = composed.get("sha256")
        verification_args = ["verify", str(record_path)]
        if scenario == "passing":
            verification_args.extend(["--sha256", str(compose_digest)])
        verify_exit, verified = _run_cli(root, environment, *verification_args)

        tamper_refusal: dict[str, Any] | None = None
        if scenario == "tampered":
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["request"] = "tampered request"
            record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            verify_exit, verified = _run_cli(
                root,
                environment,
                "verify",
                str(record_path),
                "--sha256",
                str(compose_digest),
            )
            tamper_refusal = {"exit_code": verify_exit, "status": verified.get("status"), "error": verified.get("error")}

        if scenario == "passing" and (verify_exit != 0 or verified.get("reviewable") is not True):
            raise RuntimeError(f"passing reference flow did not verify: {verified}")
        if scenario == "blocked" and (verify_exit != 0 or verified.get("reviewable") is not False):
            raise RuntimeError(f"blocked reference flow verification was ambiguous: {verified}")
        if scenario == "tampered" and (verify_exit == 0 or "digest mismatch" not in str(verified.get("error"))):
            raise RuntimeError(f"tampered reference flow was not refused: {verified}")

        stage_status = {name: ("unknown" if name == "atlas" and scenario == "blocked" else "admitted") for name in payloads}
        return {
            "schema": FLOW_SCHEMA,
            "scenario": scenario,
            "result": "pass",
            "outcome": "reviewable" if scenario == "passing" else "blocked" if scenario == "blocked" else "refused",
            "revision": REVISION,
            "stages": [
                {"name": name, "schema": payload.get("schema"), "status": stage_status[name]}
                for name, payload in payloads.items()
            ],
            "compose": {"exit_code": compose_exit, "status": compose_status, "sha256": compose_digest},
            "verification": {"exit_code": verify_exit, "reviewable": verified.get("reviewable"), "status": verified.get("status")},
            "tamper_refusal": tamper_refusal,
            "boundary": "synthetic reports only; no provider, customer, credential, or production state",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("passing", "blocked", "tampered"), default="passing")
    args = parser.parse_args(argv)
    print(json.dumps(run_flow(args.scenario), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
