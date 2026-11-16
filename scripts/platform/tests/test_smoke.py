import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_k3d


class SmokeEvidenceTests(unittest.TestCase):
    def exercise(self, ids, job_status="completed", events=True):
        calls = 0

        def request(base, method, path, key="", idem="", payload=None):
            nonlocal calls
            if path == "/health/ready":
                return 200, {"status": "ready"}
            if method == "POST":
                return (202, {"id": "run"}) if key else (401, {})
            if path.endswith("/events"):
                return 200, [
                    {"type": event}
                    for event in (["jobs_processed", "verified"] if events else ["jobs_processed"])
                ]
            if "/jobs/" in path:
                calls += 1
                return 200, {"id": path.rsplit("/", 1)[1], "status": job_status}
            return 200, {
                "status": "succeeded",
                "result": {"verified_completed": 5, "job_ids": ids},
            }

        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with (
                    patch.object(
                        verify_k3d,
                        "read_env",
                        return_value={"OPSPROOF_CONTROL_API_KEY": "test"},
                    ),
                    patch.object(verify_k3d, "http", side_effect=request),
                ):
                    verify_k3d.verify(Path("unused"))
                self.assertTrue(Path(".runtime/m5/k3d-smoke.json").is_file())
            finally:
                os.chdir(previous)
        return calls

    def test_independently_reads_all_five_jobs(self):
        self.assertEqual(self.exercise([str(i) for i in range(5)]), 5)

    def test_duplicate_ids_fail(self):
        with self.assertRaises(RuntimeError):
            self.exercise(["duplicate"] * 5)

    def test_false_completion_fails(self):
        with self.assertRaises(RuntimeError):
            self.exercise([str(i) for i in range(5)], job_status="processing")

    def test_missing_verification_event_fails(self):
        with self.assertRaises(RuntimeError):
            self.exercise([str(i) for i in range(5)], events=False)
