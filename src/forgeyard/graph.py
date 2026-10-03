"""Opaque, source-bound graph attachments for Forgeyard provenance packets.

Agent Proof owns the semantics of ``agent-proof/graph/v1``. Forgeyard owns only
the binding between that graph's digest and a Forgeyard provenance packet, so a
review packet can point at a separately verified graph without importing Agent
Proof or copying private graph payloads.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ATTACHMENT_SCHEMA = "forgeyard-provenance-graph/v1"
VERIFY_SCHEMA = "forgeyard-provenance-graph-verify/v1"
AGENT_PROOF_GRAPH_SCHEMA = "agent-proof/graph/v1"


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest(payload: dict[str, Any]) -> str:
    return _sha256(_canonical(payload))


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: root must be an object")
    return value


def _graph_summary(graph: dict[str, Any]) -> dict[str, Any]:
    if graph.get("schema") != AGENT_PROOF_GRAPH_SCHEMA:
        raise ValueError("graph attachment requires agent-proof/graph/v1")
    if not _is_sha256(graph.get("graph_sha256")) or not _is_sha256(graph.get("input_sha256")):
        raise ValueError("graph attachment requires graph and input SHA-256 values")
    for field in ("node_count", "edge_count"):
        value = graph.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"graph attachment requires a bounded {field}")
    unsigned = dict(graph)
    supplied = unsigned.pop("graph_sha256")
    if _digest(unsigned) != supplied:
        raise ValueError("graph digest mismatch")
    return {
        "schema": graph["schema"],
        "graph_sha256": graph["graph_sha256"],
        "input_sha256": graph["input_sha256"],
        "node_count": graph["node_count"],
        "edge_count": graph["edge_count"],
        "redacted": True,
    }


def build_graph_attachment(packet: Path, graph: Path) -> dict[str, Any]:
    """Bind an Agent Proof graph summary to a Forgeyard packet digest."""

    from .core import read_provenance_packet

    packet_payload = read_provenance_packet(packet)
    summary = _graph_summary(_read_object(graph, "Agent Proof graph"))
    unsigned = {
        "schema": ATTACHMENT_SCHEMA,
        "packet_sha256": packet_payload["packet_sha256"],
        "graph": summary,
    }
    return {**unsigned, "attachment_sha256": _digest(unsigned)}


def _validate_attachment(payload: dict[str, Any]) -> dict[str, Any]:
    required = {"schema", "packet_sha256", "graph", "attachment_sha256"}
    if set(payload) != required or payload.get("schema") != ATTACHMENT_SCHEMA:
        raise ValueError("invalid Forgeyard graph attachment shape")
    if not _is_sha256(payload.get("packet_sha256")) or not _is_sha256(payload.get("attachment_sha256")):
        raise ValueError("invalid Forgeyard graph attachment digest")
    if _digest({key: value for key, value in payload.items() if key != "attachment_sha256"}) != payload["attachment_sha256"]:
        raise ValueError("Forgeyard graph attachment digest mismatch")
    graph = payload["graph"]
    if not isinstance(graph, dict) or set(graph) != {"schema", "graph_sha256", "input_sha256", "node_count", "edge_count", "redacted"}:
        raise ValueError("invalid Forgeyard graph attachment summary")
    if graph["schema"] != AGENT_PROOF_GRAPH_SCHEMA or graph["redacted"] is not True:
        raise ValueError("invalid Forgeyard graph attachment summary")
    if not _is_sha256(graph["graph_sha256"]) or not _is_sha256(graph["input_sha256"]):
        raise ValueError("invalid Forgeyard graph attachment summary digest")
    for field in ("node_count", "edge_count"):
        if isinstance(graph[field], bool) or not isinstance(graph[field], int) or graph[field] < 0:
            raise ValueError("invalid Forgeyard graph attachment summary count")
    return payload


def verify_graph_attachment(
    attachment: Path,
    *,
    packet: Path | None = None,
    graph: Path | None = None,
) -> dict[str, Any]:
    """Verify attachment integrity and optionally bind packet and graph bytes."""

    try:
        payload = _validate_attachment(_read_object(attachment, "Forgeyard graph attachment"))
    except ValueError as exc:
        return {"schema": VERIFY_SCHEMA, "ok": False, "attachment_state": "invalid", "errors": [str(exc)]}
    errors: list[str] = []
    packet_state = "unbound"
    graph_state = "unbound"
    if packet is not None:
        try:
            packet_payload = _read_object(packet, "Forgeyard provenance packet")
            if packet_payload.get("packet_sha256") != payload["packet_sha256"]:
                errors.append("packet digest mismatch")
            packet_state = "verified" if not errors else "invalid"
        except ValueError as exc:
            errors.append(str(exc))
            packet_state = "invalid"
    if graph is not None:
        try:
            summary = _graph_summary(_read_object(graph, "Agent Proof graph"))
            if summary != payload["graph"]:
                errors.append("graph summary mismatch")
            graph_state = "verified" if not errors else "invalid"
        except ValueError as exc:
            errors.append(str(exc))
            graph_state = "invalid"
    if packet is None:
        errors.append("packet input is required for source-bound verification")
    if graph is None:
        errors.append("graph input is required for source-bound verification")
    return {
        "schema": VERIFY_SCHEMA,
        "ok": not errors,
        "attachment_state": "verified",
        "packet_state": packet_state,
        "graph_state": graph_state,
        "packet_sha256": payload["packet_sha256"],
        "graph_sha256": payload["graph"]["graph_sha256"],
        "errors": sorted(set(errors)),
    }


__all__ = ["ATTACHMENT_SCHEMA", "VERIFY_SCHEMA", "build_graph_attachment", "verify_graph_attachment"]
