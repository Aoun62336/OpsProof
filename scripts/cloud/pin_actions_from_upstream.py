"""Resolve GitHub Actions release refs through the official GitHub API and pin SHAs.

Requires GitHub CLI authenticated via `gh auth login`. No guessed SHA values.
Run first without --write to inspect; --write updates ONLY exact matches.
Independently review GitHub release signatures/contents before authorizing publish.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ACTION = re.compile(r"(?P<ref>[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)@(?P<tag>v\d+(?:\.\d+){0,2})")
SHA = re.compile(r"[0-9a-f]{40}")


def api(path: str) -> dict:
    result = subprocess.run(
        ["gh", "api", f"repos/{path}"], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def resolve(repo: str, tag: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repo) or not re.fullmatch(
        r"v\d+(?:\.\d+){0,2}", tag
    ):
        raise ValueError("unsafe action ref")
    obj = api(f"{repo}/git/ref/tags/{tag}")["object"]
    if obj["type"] == "tag":
        obj = api(f"{repo}/git/tags/{obj['sha']}")["object"]
    if obj["type"] != "commit" or not SHA.fullmatch(obj["sha"]):
        raise ValueError("action ref did not resolve to full commit")
    return obj["sha"]


def pin(paths: list[Path], write: bool) -> dict[str, str]:
    cache = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")

        def replace(match: re.Match) -> str:
            key = match.group(0)
            if key not in cache:
                cache[key] = resolve(match.group("ref"), match.group("tag"))
            return f"{match.group('ref')}@{cache[key]}" if write else key

        new = ACTION.sub(replace, text)
        if write:
            path.write_text(new, encoding="utf-8")
    return cache


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--write", action="store_true")
    a = p.parse_args()
    results = pin(a.paths, a.write)
    for action, sha in results.items():
        print(f"{'PINNED' if a.write else 'REVIEW'} {action} -> {sha}")
    print("UPSTREAM_TAG_RESOLUTION_COMPLETE; review commits before publishing")


if __name__ == "__main__":
    main()
