"""Verify GitHub Actions 'uses:' references are pinned to exact commit SHAs.

Does not prove the SHA belongs to the intended upstream. Verify tag->SHA via
'gh api' against upstream and review action provenance before approving.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REF = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
PIN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[a-f0-9]{40}$")


def scan(workflows: list[Path]) -> list[str]:
    issues = []
    for workflow in workflows:
        content = workflow.read_text(encoding="utf-8")
        for match in REF.finditer(content):
            reference = match.group(1)
            if not PIN.fullmatch(reference):
                issues.append(f"{workflow}: unpinned or unsupported reference {reference}")
    return issues


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("paths", nargs="+", type=Path)
    a = p.parse_args()
    issues = scan(a.paths)
    for issue in issues:
        print("FAIL:", issue)
    if issues:
        return 2
    print("PASS: Every action dependency is SHA-pinned; verify upstream identity separately")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
