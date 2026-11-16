"""Dependency-free secrets boundary tests. Never use real credentials here."""

import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

SOURCE = Path(__file__).resolve().parents[1] / "render_local_secrets.py"
spec = spec_from_file_location("secrets_renderer", SOURCE)
assert spec and spec.loader
module = module_from_spec(spec)
spec.loader.exec_module(module)


class SecretBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.values = {name: "sample-only-special-+@/%!" for name in module.REQUIRED}
        self.rendered = module.render(self.values)
        self.by_name = {
            (s["metadata"]["namespace"], s["metadata"]["name"]): s for s in self.rendered["items"]
        }

    def test_namespaces_and_secret_counts(self):
        self.assertEqual(len(self.rendered["items"]), 10)
        self.assertEqual({ns for ns, _ in self.by_name}, {"opsproof-demo", "opsproof-control"})

    def test_api_and_worker_credentials_separate(self):
        self.assertEqual(
            set(self.by_name["opsproof-demo", "opsproof-demo-runtime"]["data"]),
            {"OPSPROOF_DATABASE_URL", "OPSPROOF_REDIS_URL"},
        )
        self.assertEqual(
            set(self.by_name["opsproof-control", "opsproof-control-runtime"]["data"]),
            {
                "OPSPROOF_CONTROL_DATABASE_URL",
                "OPSPROOF_CONTROL_REDIS_URL",
                "OPSPROOF_CONTROL_TARGET_URL",
            },
        )
        self.assertEqual(
            set(self.by_name["opsproof-control", "opsproof-control-recovery"]["data"]),
            {"OPSPROOF_CONTROL_RECOVERY_KEY"},
        )

    def test_password_percent_encoding(self):
        from base64 import b64decode

        raw = self.by_name["opsproof-demo", "opsproof-demo-runtime"]["data"][
            "OPSPROOF_DATABASE_URL"
        ]
        url = b64decode(raw).decode()
        self.assertIn("%2B%40%2F%25%21", url)
        self.assertNotIn("+@/%!", url)

    def test_no_env_file_leak(self):
        with TemporaryDirectory() as temp:
            p = Path(temp) / ".env"
            p.write_text("# local\n" + "\n".join(f"{k}='{v}'" for k, v in self.values.items()))
            self.assertEqual(module.read_env(p), self.values)
            self.assertEqual(list(Path(temp).iterdir()), [p])

    def test_reject_short_secrets(self):
        self.values["OPSPROOF_RECOVERY_KEY"] = "weak"
        with self.assertRaises(ValueError):
            module.render(self.values)

    def test_reject_malformed_env(self):
        with TemporaryDirectory() as temp:
            p = Path(temp) / ".env"
            p.write_text("not a valid line\n")
            with self.assertRaises(ValueError):
                module.read_env(p)


if __name__ == "__main__":
    unittest.main()
