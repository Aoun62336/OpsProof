import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_cluster import validate_server
from preflight import GIB, blockers
from render_gitops import LOCAL_REPO, render


class FoundationTests(unittest.TestCase):
    def test_local_git_is_explicit_and_fixed(self):
        with self.assertRaises(ValueError):
            render(LOCAL_REPO, "a" * 40, "m5-" + "a" * 12)
        self.assertEqual(
            render(LOCAL_REPO, "a" * 40, "m5-" + "a" * 12, allow_local=True)["items"][1]["spec"][
                "source"
            ]["repoURL"],
            LOCAL_REPO,
        )
        with self.assertRaises(ValueError):
            render(
                "http://other.local/repo.git",
                "a" * 40,
                "m5-" + "a" * 12,
                allow_local=True,
            )

    def test_only_local_cluster_endpoint(self):
        validate_server("https://127.0.0.1:6550")
        for value in (
            "https://eks.amazonaws.com:6550",
            "https://127.0.0.1:443",
            "http://127.0.0.1:6550",
            "https://user@127.0.0.1:6550",
            "https://127.0.0.1:6550/proxy",
            "https://localhost:6550",
        ):
            with self.assertRaises(ValueError):
                validate_server(value)

    def test_resource_gate(self):
        self.assertEqual(blockers(5 * GIB, 15 * GIB, 8 * GIB, []), [])
        for memory, disk, docker in [
            (4 * GIB, 20 * GIB, 8 * GIB),
            (6 * GIB, 14 * GIB, 8 * GIB),
            (6 * GIB, 20 * GIB, 0),
        ]:
            self.assertTrue(blockers(memory, disk, docker, []))

    def test_compose_conflict(self):
        self.assertTrue(blockers(6 * GIB, 20 * GIB, 8 * GIB, ["opsproof-demo-db-1"]))
        self.assertFalse(blockers(6 * GIB, 20 * GIB, 8 * GIB, ["k3d-opsproof-server-0"]))

    def test_gitops_rejects_credentials_and_non_remote_revisions(self):
        for url, revision, tag in [
            ("https://token@github.com/org/repo", "a" * 40, "m5-" + "a" * 12),
            ("https://github.com/org/repo", "main", "m5-" + "a" * 12),
            ("https://github.com/org/repo", "a" * 40, "latest"),
            ("https://evil.example/org/repo", "a" * 40, "m5-" + "a" * 12),
        ]:
            with self.assertRaises(ValueError):
                render(url, revision, tag)

    def test_gitops_no_secret_or_rbac_ownership(self):
        record = render("https://github.com/org/repo", "a" * 40, "m5-" + "a" * 12)
        allowed = record["items"][0]["spec"]["namespaceResourceWhitelist"]
        self.assertFalse(
            any(row["kind"] in ("*", "Secret", "Role", "RoleBinding") for row in allowed)
        )
        for app in record["items"][1:]:
            self.assertFalse(app["spec"]["syncPolicy"]["automated"]["prune"])
            if app["metadata"]["name"] != "demo":
                self.assertNotIn("ignoreDifferences", app["spec"])
            else:
                rules = app["spec"]["ignoreDifferences"]
                self.assertEqual(len(rules), 3)
                for rule in rules:
                    self.assertEqual(rule["namespace"], "opsproof-demo")
                    self.assertIn(rule["name"], ("demo-release", "demo-api", "demo-api-canary"))
                    self.assertTrue(rule["jsonPointers"])
                    self.assertNotIn("jqPathExpressions", rule)


if __name__ == "__main__":
    unittest.main()
