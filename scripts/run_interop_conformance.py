#!/usr/bin/env python3
"""Run the deterministic synthetic ai-work-evidence/v1 conformance corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forgeyard.core import evidence_from_report
from forgeyard.interop import validate_evidence


def run(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    cases = []
    for case in manifest["cases"]:
        path = root / case["file"]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            validate_evidence(payload)
            valid = True
            error = None
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            valid = False
            error = str(exc)
        compose_status = None
        if valid:
            try:
                evidence = evidence_from_report(path, case["name"], "fixture-revision")
                compose_status = evidence.status.value
            except (OSError, TypeError, ValueError) as exc:
                valid = False
                error = str(exc)
        passed = valid == case["valid"] and (not valid or compose_status == case.get("compose_status"))
        cases.append({"name": case["name"], "valid": valid, "compose_status": compose_status, "error": error, "passed": passed})
    return {"schema": "forgeyard-conformance/v1", "contract": manifest["contract"], "cases": cases, "passed": all(case["passed"] for case in cases)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit the versioned report")
    args = parser.parse_args()
    report = run(Path(__file__).resolve().parents[1] / "conformance")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
