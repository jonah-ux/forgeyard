from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from forgeyard.core import WorktreeError, create_worktree, plan_worktree


with TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / "repo"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "forgeyard@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Forgeyard Fixture"], check=True)
    (source / "README.md").write_text("fixture\n")
    subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
    destination = root / "worktree"
    create_worktree(plan_worktree(source, destination))
    assert (destination / "README.md").read_text() == "fixture\n"
    detached = subprocess.run(
        ["git", "-C", str(destination), "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True,
    )
    assert detached.returncode != 0
    try:
        plan_worktree(source, source / ".worktrees" / "unsafe")
    except WorktreeError:
        pass
    else:
        raise AssertionError("unsafe nested destination admitted")

print("forgeyard detached checkout proof: PASS")
