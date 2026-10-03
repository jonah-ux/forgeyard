import hashlib
import json
from pathlib import Path

from forgeyard.core import Evidence, EvidenceStatus, TaskRecord, write_evidence_receipt, write_provenance_packet, write_record
from forgeyard.graph import build_graph_attachment, verify_graph_attachment


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _packet_fixture(tmp_path: Path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "app.py").write_text("print('synthetic')\n", encoding="utf-8")
    record = TaskRecord("graph-task", "synthetic-repo", "review graph")
    record.add_evidence(Evidence("tests", EvidenceStatus.PASS, "tests passed", "rev-1"))
    record.finalize()
    record_path = tmp_path / "record.json"
    write_record(record, record_path)
    receipt_path = tmp_path / "tests.receipt.json"
    write_evidence_receipt(record_path, "tests", ["app.py"], receipt_path)
    packet_path = tmp_path / "packet.json"
    write_provenance_packet(record_path, [receipt_path], source_root, "rev-1", ["app.py"], packet_path)
    return packet_path


def _graph_fixture(path: Path):
    graph = {
        "schema": "agent-proof/graph/v1",
        "input_sha256": "a" * 64,
        "node_count": 2,
        "edge_count": 1,
        "nodes": [],
        "edges": [],
    }
    graph["graph_sha256"] = hashlib.sha256(_canonical(graph)).hexdigest()
    path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_graph_attachment_binds_packet_and_graph_without_copying_payload(tmp_path: Path):
    packet = _packet_fixture(tmp_path)
    graph = tmp_path / "graph.json"
    _graph_fixture(graph)
    attachment = build_graph_attachment(packet, graph)
    assert attachment["schema"] == "forgeyard-provenance-graph/v1"
    assert set(attachment["graph"]) == {"schema", "graph_sha256", "input_sha256", "node_count", "edge_count", "redacted"}
    assert "nodes" not in json.dumps(attachment)
    assert verify_graph_attachment_from_payload(attachment, packet, graph)["ok"] is True


def verify_graph_attachment_from_payload(attachment, packet, graph):
    path = packet.parent / "attachment.json"
    path.write_text(json.dumps(attachment), encoding="utf-8")
    return verify_graph_attachment(path, packet=packet, graph=graph)


def test_graph_attachment_refuses_changed_graph_or_packet(tmp_path: Path):
    packet = _packet_fixture(tmp_path)
    graph = tmp_path / "graph.json"
    _graph_fixture(graph)
    attachment = build_graph_attachment(packet, graph)
    attachment_path = tmp_path / "attachment.json"
    attachment_path.write_text(json.dumps(attachment), encoding="utf-8")
    changed_graph = json.loads(graph.read_text(encoding="utf-8"))
    changed_graph["node_count"] = 3
    changed_graph_path = tmp_path / "changed-graph.json"
    changed_graph_path.write_text(json.dumps(changed_graph), encoding="utf-8")
    result = verify_graph_attachment(attachment_path, packet=packet, graph=changed_graph_path)
    assert result["ok"] is False
    assert "graph digest mismatch" in result["errors"]
    changed_packet = json.loads(packet.read_text(encoding="utf-8"))
    changed_packet["packet_sha256"] = "b" * 64
    changed_packet_path = tmp_path / "changed-packet.json"
    changed_packet_path.write_text(json.dumps(changed_packet), encoding="utf-8")
    result = verify_graph_attachment(attachment_path, packet=changed_packet_path, graph=graph)
    assert result["ok"] is False
    assert "packet digest mismatch" in result["errors"]


def test_graph_attachment_refuses_resealed_attachment_without_bound_inputs(tmp_path: Path):
    packet = _packet_fixture(tmp_path)
    graph = tmp_path / "graph.json"
    _graph_fixture(graph)
    attachment = build_graph_attachment(packet, graph)
    attachment["graph"]["node_count"] = 99
    unsigned = {key: value for key, value in attachment.items() if key != "attachment_sha256"}
    attachment["attachment_sha256"] = hashlib.sha256(_canonical(unsigned)).hexdigest()
    path = tmp_path / "resealed.json"
    path.write_text(json.dumps(attachment), encoding="utf-8")
    result = verify_graph_attachment(path, packet=packet, graph=graph)
    assert result["ok"] is False
    assert "graph summary mismatch" in result["errors"]
