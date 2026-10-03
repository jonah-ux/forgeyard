import importlib.util
from pathlib import Path
import tempfile


def _module():
    path = Path(__file__).parents[1] / "scripts" / "audit_public_surface.py"
    spec = importlib.util.spec_from_file_location("audit_public_surface", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_audit_passes_static_surface_and_marks_missing_artifacts_unavailable():
    report = _module().audit()
    assert report["schema"] == "forgeyard-public-audit/v1"
    assert report["result"] == "pass"
    assert report["dependency_inventory"]["state"] == "pass"
    assert report["license_inventory"]["state"] == "pass"
    assert report["release_provenance"]["state"] == "pass"
    assert report["privacy_scan"]["state"] == "pass"
    assert report["artifact_audit"]["state"] == "unavailable"


def test_public_audit_flags_high_signal_private_key(tmp_path):
    module = _module()
    original = module._tracked_files
    fake = tmp_path / "fixture.txt"
    fake.write_bytes(b"-----BEGIN " + b"PRIVATE KEY-----\nsynthetic\n")
    module._tracked_files = lambda: [fake]
    try:
        result = module._secret_scan()
    finally:
        module._tracked_files = original
    assert result["state"] == "blocked"
    assert result["findings"] == [{"path": "fixture.txt", "class": "private_key"}]


def test_public_audit_blocks_checksum_mismatch(tmp_path):
    module = _module()
    (tmp_path / "demo.whl").write_bytes(b"wheel")
    (tmp_path / "demo.tar.gz").write_bytes(b"sdist")
    (tmp_path / "SHA256SUMS").write_text("0" * 64 + "  demo.whl\n" + "1" * 64 + "  demo.tar.gz\n", encoding="utf-8")
    report = module.audit(tmp_path)
    assert report["artifact_audit"]["state"] == "blocked"
    assert report["result"] == "blocked"
