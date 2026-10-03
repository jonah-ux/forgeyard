"""Minimal noninteractive CLI for the first Forgeyard vertical slice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from . import __version__
from .core import (
    Evidence,
    EvidenceStatus,
    TaskRecord,
    TaskStatus,
    evidence_from_report,
    build_review_packet,
    create_worktree,
    plan_worktree,
    read_record,
    verify_record,
    verify_provenance_packet,
    write_evidence_receipt,
    write_record,
    write_provenance_packet,
)
from .graph import build_graph_attachment, verify_graph_attachment


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
    compose = sub.add_parser("compose", help="compose specialist JSON reports into a review record")
    compose.add_argument("--task-id", required=True)
    compose.add_argument("--repository", required=True)
    compose.add_argument("--request", required=True)
    compose.add_argument("--input", action="append", required=True, metavar="NAME=REPORT.json")
    compose.add_argument("--revision")
    compose.add_argument("--output", type=Path, required=True)
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
    verify.add_argument("--sha256", help="require the record to match this SHA-256 digest")
    review = sub.add_parser("review", help="build a review packet from a verified record")
    review.add_argument("record", type=Path)
    review.add_argument("--sha256", help="require the review packet to use this exact record digest")
    review.add_argument("--revision", required=True)
    review.add_argument("--path", action="append", required=True, dest="changed_paths")
    sub.add_parser("demo", help="run the offline evidence-to-review walkthrough")
    receipt = sub.add_parser("receipt", help="write one source-bound evidence receipt")
    receipt.add_argument("record", type=Path)
    receipt.add_argument("--name", required=True)
    receipt.add_argument("--path", action="append", required=True, dest="source_paths")
    receipt.add_argument("--output", type=Path, required=True)
    packet = sub.add_parser("packet", help="write a portable multi-source provenance packet")
    packet.add_argument("record", type=Path)
    packet.add_argument("--receipt", action="append", required=True, dest="receipts")
    packet.add_argument("--source-root", type=Path, required=True)
    packet.add_argument("--revision", required=True)
    packet.add_argument("--path", action="append", required=True, dest="changed_paths")
    packet.add_argument("--output", type=Path, required=True)
    verify_packet = sub.add_parser("verify-packet", help="verify a portable provenance packet")
    verify_packet.add_argument("packet", type=Path)
    verify_packet.add_argument("--source-root", type=Path)
    graph_attach = sub.add_parser("graph-attach", help="bind an Agent Proof graph summary to a provenance packet")
    graph_attach.add_argument("packet", type=Path)
    graph_attach.add_argument("graph", type=Path)
    graph_attach.add_argument("--output", type=Path, required=True)
    verify_graph = sub.add_parser("verify-graph-attachment", help="verify a packet/graph attachment")
    verify_graph.add_argument("attachment", type=Path)
    verify_graph.add_argument("--packet", type=Path)
    verify_graph.add_argument("--graph", type=Path)
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
    if args.command == "compose":
        record = TaskRecord(args.task_id, args.repository, args.request)
        try:
            for raw in args.input:
                name, separator, path = raw.partition("=")
                if not separator or not name or not path:
                    raise ValueError("specialist input must use NAME=REPORT.json")
                record.add_evidence(evidence_from_report(Path(path), name, args.revision))
            record.finalize()
            digest = write_record(record, args.output)
        except (OSError, ValueError) as exc:
            print(json.dumps({"schema": "forgeyard-compose/v1", "status": "invalid", "error": str(exc)}))
            return 2
        print(json.dumps({"schema": "forgeyard-compose/v1", "record": str(args.output), "sha256": digest, "status": record.status.value}, sort_keys=True))
        return 0 if record.status is TaskStatus.READY_FOR_REVIEW else 2
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
            print(json.dumps(verify_record(args.record, args.sha256), sort_keys=True))
        except ValueError as exc:
            print(json.dumps({"schema": "forgeyard-record-verify/v1", "status": "invalid", "error": str(exc)}))
            return 2
        return 0
    if args.command == "review":
        try:
            verification = verify_record(args.record, args.sha256)
            packet = build_review_packet(read_record(args.record), args.revision, args.changed_paths)
            packet["record_sha256"] = verification["sha256"]
        except ValueError as exc:
            print(json.dumps({"schema": "forgeyard-review-packet/v1", "status": "invalid", "error": str(exc)}))
            return 2
        print(json.dumps(packet, sort_keys=True))
        return 0
    if args.command == "demo":
        with tempfile.TemporaryDirectory(prefix="forgeyard-demo-") as directory:
            record_path = Path(directory) / "demo-record.json"
            record = TaskRecord("demo-001", "fixture-repo", "add a feature")
            record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "3 passed", "demo-revision"))
            record.add_evidence(Evidence("diff", EvidenceStatus.PASS, "clean diff", "demo-revision"))
            record.finalize()
            digest = write_record(record, record_path)
            verification = verify_record(record_path, digest)
            packet = build_review_packet(read_record(record_path), "demo-revision", ["src/example.py"])
            packet["record_sha256"] = verification["sha256"]
            print(json.dumps({"schema": "forgeyard-demo/v1", "verification": verification, "review_packet": packet}, sort_keys=True))
        return 0
    if args.command == "receipt":
        try:
            digest = write_evidence_receipt(args.record, args.name, args.source_paths, args.output)
        except (OSError, ValueError) as exc:
            print(json.dumps({"schema": "forgeyard-evidence-receipt/v1", "status": "invalid", "error": str(exc)}))
            return 2
        print(json.dumps({"receipt": str(args.output), "sha256": digest, "status": "written"}, sort_keys=True))
        return 0
    if args.command == "packet":
        try:
            digest = write_provenance_packet(
                args.record,
                [Path(value) for value in args.receipts],
                args.source_root,
                args.revision,
                args.changed_paths,
                args.output,
            )
        except (OSError, ValueError) as exc:
            print(json.dumps({"schema": "forgeyard-provenance-packet/v1", "status": "invalid", "error": str(exc)}))
            return 2
        print(json.dumps({"packet": str(args.output), "packet_sha256": digest, "status": "written"}, sort_keys=True))
        return 0
    if args.command == "verify-packet":
        result = verify_provenance_packet(args.packet, args.source_root)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 1
    if args.command == "graph-attach":
        try:
            attachment = build_graph_attachment(args.packet, args.graph)
            args.output.write_text(json.dumps(attachment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except (OSError, ValueError) as exc:
            print(json.dumps({"schema": "forgeyard-provenance-graph/v1", "status": "invalid", "error": str(exc)}))
            return 2
        print(json.dumps({"schema": "forgeyard-provenance-graph/v1", "attachment": str(args.output), "attachment_sha256": attachment["attachment_sha256"], "status": "written"}, sort_keys=True))
        return 0
    if args.command == "verify-graph-attachment":
        result = verify_graph_attachment(args.attachment, packet=args.packet, graph=args.graph)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
