import hashlib
import tempfile
from pathlib import Path
from unittest import TestCase

from scripts.reliability.acceptance_audit import REQUIRED, audit


class AuditTests(TestCase):
    def test_all_six_require_independent_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = []
            for scenario in sorted(REQUIRED):
                artifacts = []
                for n in (1, 2):
                    relative = f".runtime/m6/{scenario}/{n}.json"
                    f = root / relative
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text(f'{{"sample": "{scenario}-{n}"}}')
                    artifacts.append(
                        {
                            "path": relative,
                            "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                        }
                    )
                records.append({"scenario": scenario, "artifacts": artifacts})
            manifest = {"source_sha": "a" * 40, "scenarios": records}
            result = audit(manifest, root)
            self.assertTrue(result["operator_acceptance_required"])
            self.assertEqual(result["live_acceptance"], "NOT_CERTIFIED_BY_OFFLINE_AUDIT")
            records[0]["artifacts"][0]["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                audit(manifest, root)

    def test_no_scenario_can_be_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                audit({"source_sha": "a" * 40, "scenarios": []}, Path(temp))
