#!/usr/bin/env python3
"""Run the offline Agent Systems Lab reference flow through Forgeyard's CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from typing import Any


REVISION = "agent-systems-lab-fixture-revision"
FLOW_SCHEMA = "forgeyard-reference-flow/v1"
INSTALLED_FLOW_SCHEMA = "forgeyard-installed-reference-flow/v1"
INSTALLED_REVISION = "agent-systems-lab-installed-revision"


class InstalledFlowUnavailable(RuntimeError):
    """Raised when an explicitly requested installed producer is unavailable."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _command(value: str) -> list[str]:
    parts = shlex.split(value)
    if not parts:
        raise ValueError("command prefix must not be empty")
    return parts


def _bounded_command_record(label: str, result: subprocess.CompletedProcess[str], version: str | None = None) -> dict[str, Any]:
    return {
        "name": label,
        "exit_code": result.returncode,
        "stdout_sha256": _sha256(result.stdout.encode("utf-8")),
        "stderr_sha256": _sha256(result.stderr.encode("utf-8")),
        "version": version,
    }


def _json_stdout(label: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} emitted non-JSON output") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} emitted a non-object JSON result")
    return value


def _run_external(
    label: str,
    prefix: list[str],
    *arguments: str,
    allowed_exit_codes: tuple[int, ...] = (0,),
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        result = subprocess.run(
            [*prefix, *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise InstalledFlowUnavailable(f"{label} command is unavailable") from exc
    metadata = _bounded_command_record(label, result)
    if result.returncode not in allowed_exit_codes:
        raise RuntimeError(f"{label} exited {result.returncode}")
    return _json_stdout(label, result), metadata


def _version(prefix: list[str], label: str) -> tuple[str, dict[str, Any]]:
    try:
        result = subprocess.run([*prefix, "--version"], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise InstalledFlowUnavailable(f"{label} command is unavailable") from exc
    if result.returncode != 0:
        raise InstalledFlowUnavailable(f"{label} did not provide a version")
    value = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    if not value or len(value) > 160:
        raise InstalledFlowUnavailable(f"{label} returned an unusable version")
    return value, _bounded_command_record(label, result, value)


def _installed_flow(
    scenario: str,
    *,
    chatlens_trace: Path,
    atlas_state: Path,
    command_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run the opt-in installed-package handoff against owner-produced files."""

    if not chatlens_trace.is_file() or not atlas_state.is_file():
        raise InstalledFlowUnavailable("installed mode requires readable ChatLens trace and Atlas state files")
    configured = command_map or {
        "chatlens": "chatlens",
        "atlas": "atlas",
        "agent_proof": "agent-proof",
        "forgeyard": "forgeyard",
    }
    commands = {name: _command(value) for name, value in configured.items()}
    versions: dict[str, str] = {}
    command_receipts: list[dict[str, Any]] = []
    for name in ("chatlens", "atlas", "agent_proof", "forgeyard"):
        versions[name], receipt = _version(commands[name], name)
        command_receipts.append(receipt)

    with tempfile.TemporaryDirectory(prefix="forgeyard-installed-flow-") as directory:
        work = Path(directory)
        chatlens_evidence = work / "chatlens-evidence.json"
        atlas_evidence = work / "atlas-evidence.json"
        chatlens_trace_result, receipt = _run_external(
            "chatlens-trace-import",
            commands["chatlens"],
            "trace-import",
            str(chatlens_trace),
            "--json",
        )
        command_receipts.append(receipt)
        if chatlens_trace_result.get("ok") is not True:
            raise RuntimeError("ChatLens trace import was not verified")

        _, receipt = _run_external(
            "chatlens-evidence-export",
            commands["chatlens"],
            "evidence-export",
            str(chatlens_trace),
            "--id",
            "installed-flow:chatlens",
            "--subject",
            "Synthetic installed ChatLens trace",
            "--summary",
            "Bounded installed-package handoff",
            "--created-at",
            "2026-01-01T00:00:00Z",
            "--fixture-id",
            "agent-systems-lab-installed",
            "--out",
            str(chatlens_evidence),
            "--json",
        )
        command_receipts.append(receipt)

        _, receipt = _run_external(
            "atlas-evidence",
            commands["atlas"],
            "evidence",
            "demo-task",
            "--state",
            str(atlas_state),
            "--id",
            "installed-flow:atlas",
            "--created-at",
            "2026-01-01T00:00:00Z",
            "--subject",
            "Synthetic installed Atlas receipt",
            "--summary",
            "Bounded installed-package handoff",
            "--fixture",
            "agent-systems-lab-installed",
            "--out",
            str(atlas_evidence),
        )
        command_receipts.append(receipt)

        if scenario == "blocked":
            atlas_payload = json.loads(atlas_evidence.read_text(encoding="utf-8"))
            atlas_payload["status"] = "unknown"
            atlas_evidence.write_text(json.dumps(atlas_payload, sort_keys=True) + "\n", encoding="utf-8")

        interop_paths: dict[str, Path] = {}
        interop_results: dict[str, dict[str, Any]] = {}
        for name, source in (("chatlens", chatlens_evidence), ("atlas", atlas_evidence)):
            output = work / f"{name}-interop.json"
            normalized, receipt = _run_external(
                f"agent-proof-normalize-{name}",
                commands["agent_proof"],
                "normalize",
                str(source),
                "--artifact-root",
                str(work),
                "--out",
                str(output),
            )
            command_receipts.append(receipt)
            verified, receipt = _run_external(
                f"agent-proof-verify-{name}",
                commands["agent_proof"],
                "verify-interop",
                str(output),
                "--artifact-root",
                str(work),
                "--require-input",
            )
            command_receipts.append(receipt)
            if verified.get("ok") is not True:
                raise RuntimeError(f"Agent Proof did not source-verify {name} evidence")
            interop_paths[name] = output
            interop_results[name] = {"schema": normalized.get("schema"), "source_state": verified.get("source_state")}

        record_path = work / "installed-record.json"
        compose_args = [
            "compose",
            "--task-id",
            f"installed-reference-flow-{scenario}",
            "--repository",
            "agent-systems-lab-installed",
            "--request",
            "admit installed synthetic agent work",
            "--revision",
            INSTALLED_REVISION,
            "--output",
            str(record_path),
            "--input",
            f"chatlens={interop_paths['chatlens']}",
            "--input",
            f"atlas={atlas_evidence if scenario == 'blocked' else interop_paths['atlas']}",
        ]
        composed, receipt = _run_external(
            "forgeyard-compose",
            commands["forgeyard"],
            *compose_args,
            allowed_exit_codes=(0, 2),
        )
        command_receipts.append(receipt)
        compose_exit = receipt["exit_code"]
        if scenario == "passing" and (compose_exit != 0 or composed.get("status") != "ready_for_review"):
            raise RuntimeError("installed passing flow did not compose")
        if scenario == "blocked" and (compose_exit != 2 or composed.get("status") != "blocked"):
            raise RuntimeError("installed blocked flow did not refuse")

        compose_digest = composed.get("sha256")
        verified, verify_receipt = _run_external(
            "forgeyard-verify",
            commands["forgeyard"],
            "verify",
            str(record_path),
            "--sha256",
            str(compose_digest),
        )
        command_receipts.append(verify_receipt)
        tamper_refusal: dict[str, Any] | None = None
        if scenario == "tampered":
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["request"] = "tampered installed request"
            record_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
            tampered, tamper_receipt = _run_external(
                "forgeyard-verify-tampered",
                commands["forgeyard"],
                "verify",
                str(record_path),
                "--sha256",
                str(compose_digest),
                allowed_exit_codes=(1, 2),
            )
            command_receipts.append(tamper_receipt)
            tamper_refusal = {"status": tampered.get("status"), "error": tampered.get("error"), "exit_code": tamper_receipt["exit_code"]}

        return {
            "schema": INSTALLED_FLOW_SCHEMA,
            "scenario": scenario,
            "result": "pass",
            "outcome": "reviewable" if scenario == "passing" else "blocked" if scenario == "blocked" else "refused",
            "revision": INSTALLED_REVISION,
            "source_mode": "installed-owner-artifacts",
            "versions": versions,
            "stages": [
                {"name": "chatlens", "status": "source_verified", **interop_results["chatlens"]},
                {"name": "atlas", "status": "unknown" if scenario == "blocked" else "source_verified", **interop_results["atlas"]},
                {"name": "forgeyard", "status": composed.get("status")},
            ],
            "commands": command_receipts,
            "compose": {"exit_code": compose_exit, "status": composed.get("status"), "sha256": compose_digest},
            "verification": {"exit_code": verify_receipt["exit_code"], "reviewable": verified.get("reviewable"), "status": verified.get("status")},
            "tamper_refusal": tamper_refusal,
            "boundary": "owner-produced synthetic artifacts only; no provider, customer, credential, or production state",
        }


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
    parser.add_argument("--mode", choices=("fixture", "installed"), default="fixture")
    parser.add_argument("--scenario", choices=("passing", "blocked", "tampered"), default="passing")
    parser.add_argument("--chatlens-trace", type=Path, help="owner-produced ChatLens trace for --mode installed")
    parser.add_argument("--atlas-state", type=Path, help="owner-produced Atlas state JSONL for --mode installed")
    parser.add_argument("--chatlens-command", default="chatlens")
    parser.add_argument("--atlas-command", default="atlas")
    parser.add_argument("--agent-proof-command", default="agent-proof")
    parser.add_argument("--forgeyard-command", default="forgeyard")
    args = parser.parse_args(argv)
    if args.mode == "fixture":
        payload = run_flow(args.scenario)
    else:
        if args.chatlens_trace is None or args.atlas_state is None:
            parser.error("--mode installed requires --chatlens-trace and --atlas-state")
        try:
            payload = _installed_flow(
                args.scenario,
                chatlens_trace=args.chatlens_trace.expanduser().resolve(),
                atlas_state=args.atlas_state.expanduser().resolve(),
                command_map={
                    "chatlens": args.chatlens_command,
                    "atlas": args.atlas_command,
                    "agent_proof": args.agent_proof_command,
                    "forgeyard": args.forgeyard_command,
                },
            )
        except InstalledFlowUnavailable as exc:
            payload = {
                "schema": INSTALLED_FLOW_SCHEMA,
                "scenario": args.scenario,
                "result": "unavailable",
                "outcome": "unavailable",
                "error": str(exc),
                "boundary": "installed owner artifacts and commands are required; no fallback fixture was substituted",
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 3
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
