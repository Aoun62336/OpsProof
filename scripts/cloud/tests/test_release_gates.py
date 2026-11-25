"""Offline M7 acceptance guards. No AWS, GitHub or Kubernetes operations."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.cloud.build_public_replay import CASES
from scripts.cloud.check_workflow_pins import scan
from scripts.cloud.verify_public_replay import audit
from scripts.cloud.verify_release_manifest import validate


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "source_sha": "a" * 40,
            "repository": "example/opsproof",
            "workflow_run_id": 123,
            "images": {
                role: f"ghcr.io/example/opsproof/opsproof-{role}@sha256:{i * 64}"
                for role, i in (
                    ("demo", "a"),
                    ("control", "b"),
                    ("web", "c"),
                    ("edge", "d"),
                    ("grafana", "e"),
                )
            },
        }

    def test_exact_immutable_digests(self):
        self.assertEqual(validate(self.record)["status"], "FORMAT_VALIDATED_NOT_REGISTRY_VERIFIED")

    def test_rejects_mutable_tag(self):
        self.record["images"]["web"] = "ghcr.io/example/opsproof/opsproof-web:latest"
        with self.assertRaises(ValueError):
            validate(self.record)

    def test_rejects_wrong_owner(self):
        self.record["images"]["web"] = f"ghcr.io/other/opsproof/opsproof-web@sha256:{'c' * 64}"
        with self.assertRaises(ValueError):
            validate(self.record)


class PublicTests(unittest.TestCase):
    BASE = (
        '<html><head><meta http-equiv="content-security-policy" '
        "content=\"default-src 'none'\"></head><body>"
    )

    def test_six_curated_cases(self):
        data = (
            self.BASE
            + "".join(f'<article id="{case}" data-scenario="{case}"></article>' for case in CASES)
            + "</body></html>"
        )
        self.assertEqual(audit(data)["cases"], 6)

    def test_duplicate_scenarios_do_not_pass_as_six_cases(self):
        with self.assertRaises(ValueError):
            audit(self.BASE + '<article id="same" data-scenario="worker_failure"></article>' * 6)

    def test_rejects_script(self):
        with self.assertRaises(ValueError):
            audit(self.BASE + "<script>alert(1)</script>" + "<article></article>" * 6)

    def test_rejects_private_address(self):
        with self.assertRaises(ValueError):
            audit(self.BASE + "localhost:8081" + "<article></article>" * 6)


class PinTests(unittest.TestCase):
    def test_unpinned_action_rejected(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "workflow.yml"
            path.write_text("steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
            self.assertEqual(len(scan([path])), 1)

    def test_sha_pin_accepted(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "workflow.yml"
            path.write_text(f"steps:\n  - uses: actions/checkout@{'f' * 40}\n", encoding="utf-8")
            self.assertEqual(scan([path]), [])


if __name__ == "__main__":
    unittest.main()
