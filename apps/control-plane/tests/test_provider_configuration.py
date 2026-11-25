"""Recovery Compose must retain the supported disabled provider defaults."""

import re
from pathlib import Path

from opsproof_control.config import Settings


def test_recovery_defaults_match_application_and_example():
    root = Path(__file__).resolve().parents[3]
    source = (root / "compose.control.recovery.yaml").read_text()
    example = dict(
        line.split("=", 1)
        for line in (root / ".env.example").read_text().splitlines()
        if line and not line.startswith("#")
    )
    for field in ("ai_provider", "ai_model", "ai_enabled"):
        setting = "OPSPROOF_CONTROL_" + field.upper()
        expected = Settings.model_fields[field].default
        expected = str(expected).lower() if isinstance(expected, bool) else expected
        defaults = re.findall(r"\$\{" + setting + r":-([^}]+)\}", source)
        assert defaults and all(value == expected for value in defaults)
        assert example[setting] == expected
