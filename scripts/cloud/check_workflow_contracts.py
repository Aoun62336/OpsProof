"""Check static repository inputs and cloud test discovery in maintained workflows.

This complements actionlint and SHA pin checks. It does not execute shell blocks,
validate downloaded files, or establish a successful hosted workflow run.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = re.compile(
    r"(?<![\w/])(?:apps|scripts|docs|infra|observability|benchmarks)/"
    r"[A-Za-z0-9_./-]+\.(?:py|sh|json|toml|yaml|yml|hcl)\b"
)


def check(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    issues = []
    for workflow in sorted((root / ".github/workflows").glob("*.yml")):
        for number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for match in SOURCE_PATH.finditer(line):
                relative = match.group()
                target = (root / relative).resolve()
                if not target.is_relative_to(root) or not target.is_file():
                    issues.append(
                        f"{workflow.name}:{number}: missing/unsafe source input {relative}"
                    )
            if "scripts/cloud/tests" in line and re.search(r"\bunittest\s+discover\b", line):
                issues.append(
                    f"{workflow.name}:{number}: cloud tests require pytest discovery "
                    "to include function-based and parameterized cases"
                )
    return issues


def main() -> int:
    issues = check()
    for issue in issues:
        print("FAIL:", issue)
    if issues:
        return 1
    print("PASS: static workflow source inputs exist and cloud tests use complete discovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
