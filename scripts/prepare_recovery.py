"""Add missing local recovery credentials without disclosing or replacing them."""

from pathlib import Path
from secrets import token_urlsafe

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    path = ROOT / ".env"
    if not path.exists():
        raise SystemExit("Root .env missing. Restore existing local configuration first.")
    content = path.read_text(encoding="utf-8")
    names = {
        line.partition("=")[0].strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    values = {
        "OPSPROOF_INSPECTION_KEY": token_urlsafe(32),
        "OPSPROOF_RECOVERY_KEY": token_urlsafe(32),
        "OPSPROOF_CONTROL_RECOVERY_ENABLED": "false",
        "OPSPROOF_CONTROL_AI_ENABLED": "false",
    }
    additions = [f"{name}={value}" for name, value in values.items() if name not in names]
    if additions:
        with path.open("a", encoding="utf-8") as output:
            output.write("\n" if content and not content.endswith("\n") else "")
            output.write("\n".join(additions) + "\n")
    print("Missing recovery settings prepared; existing values preserved.")


if __name__ == "__main__":
    main()
