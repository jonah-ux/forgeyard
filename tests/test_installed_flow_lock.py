import json
from pathlib import Path
import re
import unittest


LOCK = Path(__file__).parents[1] / "conformance" / "installed-flow-release-lock-v1.json"


class InstalledFlowReleaseLockTests(unittest.TestCase):
    def test_lock_is_sorted_complete_and_hash_pinned(self):
        payload = json.loads(LOCK.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "forgeyard-installed-flow-release-lock/v1")
        packages = payload["packages"]
        self.assertEqual([item["name"] for item in packages], sorted(item["name"] for item in packages))
        self.assertEqual({item["name"] for item in packages}, {"agent-proof", "atlas-agent-runtime", "chatlens", "forgeyard"})
        for package in packages:
            self.assertRegex(package["commit"], r"^[0-9a-f]{40}$")
            self.assertTrue(package["release"].startswith("https://github.com/"))
            self.assertIn(package["channel"], {"stable", "prerelease"})
            self.assertIn(package["cli"], {"chatlens", "atlas", "agent-proof", "forgeyard"})
            for artifact in package["artifacts"].values():
                self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(payload["observation"]["source_mode"], "public-main-editable")
        self.assertEqual(payload["observation"]["runtime"], "python-3.14")
        self.assertEqual(set(payload["observation"]["revisions"]), {"chatlens", "atlas-agent-runtime", "agent-proof", "forgeyard"})
        for revision in payload["observation"]["revisions"].values():
            self.assertRegex(revision, r"^[0-9a-f]{40}$")
        self.assertEqual(set(payload["observation"]["outcomes"]), {"reviewable", "blocked", "tampered-digest-refused"})


if __name__ == "__main__":
    unittest.main()
