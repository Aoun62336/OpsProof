import unittest
from scripts.m7.build_public_replay import build


class ReplayTests(unittest.TestCase):
    def test_empty_is_explicit_not_a_fake_success(self):
        result = build([])
        self.assertIn("No curated evidence", result)
        self.assertNotIn("fetch(", result)

    def test_rejects_secrets_and_injected_html(self):
        case = {
            "id": "worker-test-001", "scenario": "worker_failure", "title": "Safe test",
            "environment": "local-k3d", "source_commit": "a" * 40,
            "status": "failed", "observed_utc": "2026-11-08T12:00:00Z",
            "summary": "Observed a synthetic interruption", "findings": ["Job state checked"],
            "limitations": "Only local validation", "source_evidence_sha256": "b" * 64,
        }
        for dangerous in ("password=secret", "person@example.org", "Bearer abc.def.ghi"):
            with self.subTest(dangerous=dangerous), self.assertRaises(ValueError):
                build([{**case, "summary": dangerous}])
        rendered = build([{**case, "summary": "<img src=x onerror=alert(1)>"}])
        self.assertIn("&lt;img", rendered)
        self.assertNotIn('<img src=x', rendered)

    def test_requires_exact_fields(self):
        with self.assertRaises(ValueError):
            build([{"id": "fake"}])


if __name__ == "__main__":
    unittest.main()
