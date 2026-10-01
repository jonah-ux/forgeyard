"""Minimal noninteractive CLI for the first Forgeyard vertical slice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .core import Evidence, EvidenceStatus, TaskRecord, write_record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forgeyard")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="create a task evidence record")
    create.add_argument("--task-id", required=True)
    create.add_argument("--repository", required=True)
    create.add_argument("--request", required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--evidence", action="append", default=[], metavar="NAME=STATUS:DETAIL")
    return parser


def parse_evidence(raw: str) -> Evidence:
    try:
        name_status, detail = raw.split(":", 1)
        name, status = name_status.split("=", 1)
        return Evidence(name=name, status=EvidenceStatus(status), detail=detail)
    except (ValueError, KeyError) as exc:
        raise SystemExit(f"invalid evidence {raw!r}; expected NAME=pass|fail|unknown|skipped:DETAIL") from exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create":
        record = TaskRecord(args.task_id, args.repository, args.request)
        for raw in args.evidence:
            record.add_evidence(parse_evidence(raw))
        record.finalize()
        digest = write_record(record, args.output)
        print(json.dumps({"record": str(args.output), "sha256": digest, "status": record.status.value}))
        return 0 if record.status.value == "ready_for_review" else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
