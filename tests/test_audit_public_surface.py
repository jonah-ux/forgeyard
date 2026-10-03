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


def test_public_audit_rejects_incomplete_requested_artifacts_and_comment_markers(tmp_path):
    module = _module()
    assert module.audit(require_dist=True)["result"] == "blocked"
    assert module.audit(tmp_path)["result"] == "blocked"
    (tmp_path / "demo.whl").write_bytes(b"wheel")
    (tmp_path / "demo.tar.gz").write_bytes(b"sdist")
    (tmp_path / "SHA256SUMS").write_text("garbage\n", encoding="utf-8")
    assert module.audit(tmp_path)["result"] == "blocked"
    original_root = module.ROOT
    try:
        module.ROOT = tmp_path
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        (tmp_path / ".github" / "workflows" / "release.yml").write_text("# SHA256SUMS refs/tags build gh release\n", encoding="utf-8")
        (tmp_path / "PROVENANCE.md").write_text("public provenance", encoding="utf-8")
        (tmp_path / "SECURITY.md").write_text("public security", encoding="utf-8")
        assert module._release_provenance()["state"] == "blocked"
    finally:
        module.ROOT = original_root


def test_public_audit_blocks_empty_tracked_file_scan():
    module = _module()
    original = module._tracked_files
    module._tracked_files = lambda: []
    try:
        assert module._secret_scan()["state"] == "blocked"
    finally:
        module._tracked_files = original


def test_public_audit_blocks_structurally_invalid_project_metadata(tmp_path):
    module = _module()
    original_root = module.ROOT
    try:
        module.ROOT = tmp_path
        (tmp_path / "pyproject.toml").write_text('project = "malformed"\n[build-system]\nrequires = []\n', encoding="utf-8")
        assert module._dependency_inventory()["state"] == "blocked"
    finally:
        module.ROOT = original_root
