"""Minimal noninteractive CLI for the first Forgeyard vertical slice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .core import Evidence, EvidenceStatus, TaskRecord, build_review_packet, create_worktree, plan_worktree, read_record, verify_record, write_record


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
    worktree = sub.add_parser("plan-worktree", help="validate an isolated worktree request")
    worktree.add_argument("--source", type=Path, required=True)
    worktree.add_argument("--destination", type=Path, required=True)
    worktree.add_argument("--revision", default="HEAD")
    create_worktree_cmd = sub.add_parser("create-worktree", help="create a planned isolated worktree")
    create_worktree_cmd.add_argument("--source", type=Path, required=True)
    create_worktree_cmd.add_argument("--destination", type=Path, required=True)
    create_worktree_cmd.add_argument("--revision", default="HEAD")
    verify = sub.add_parser("verify", help="verify a task evidence record")
    verify.add_argument("record", type=Path)
    review = sub.add_parser("review", help="build a review packet from a verified record")
    review.add_argument("record", type=Path)
    review.add_argument("--revision", required=True)
    review.add_argument("--path", action="append", required=True, dest="changed_paths")
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
    if args.command == "plan-worktree":
        try:
            plan = plan_worktree(args.source, args.destination, args.revision)
        except ValueError as exc:
            print(json.dumps({"status": "blocked", "error": str(exc)}))
            return 2
        print(json.dumps({"status": "planned", "command": plan.command()}))
        return 0
    if args.command == "create-worktree":
        try:
            plan = plan_worktree(args.source, args.destination, args.revision)
            create_worktree(plan)
        except ValueError as exc:
            print(json.dumps({"status": "blocked", "error": str(exc)}))
            return 2
        print(json.dumps({"status": "created", "source": str(plan.source), "destination": str(plan.destination), "revision": plan.revision}))
        return 0
    if args.command == "verify":
        try:
            print(json.dumps(verify_record(args.record), sort_keys=True))
        except ValueError as exc:
            print(json.dumps({"schema": "forgeyard-record-verify/v1", "status": "invalid", "error": str(exc)}))
            return 2
        return 0
    if args.command == "review":
        try:
            packet = build_review_packet(read_record(args.record), args.revision, args.changed_paths)
        except ValueError as exc:
            print(json.dumps({"schema": "forgeyard-review-packet/v1", "status": "invalid", "error": str(exc)}))
            return 2
        print(json.dumps(packet, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
