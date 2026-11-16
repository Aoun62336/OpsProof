"""Fail-closed static HTML audit for manually reviewed evidence replay.

A passing audit does NOT make content safe for publication: human review remains
mandatory. Prevents obvious accidental live links and script-enabled surfaces.
"""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path

from scripts.cloud.build_public_replay import CASES

DANGEROUS = re.compile(
    r"(?i)(?:AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|"
    r"\b(?:password|api[_-]?key|authorization|set-cookie)\s*[:=]|"
    r"\bBearer\s+[a-z0-9._-]+|(?:https?://)?(?:localhost|127\.0\.0\.1)(?::\d+)?|"
    r"https?://(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)|"
    r"<%|\$\{\{|\{\{\s*secrets\.)"
)
FORBIDDEN = {
    "script",
    "iframe",
    "form",
    "input",
    "button",
    "object",
    "embed",
    "audio",
    "video",
    "canvas",
    "svg",
    "base",
    "link",
}
URL_ATTRIBUTES = {"src", "href", "action", "formaction", "srcdoc"}


class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.articles = 0
        self.scenarios: list[str | None] = []
        self.ids: list[str | None] = []
        self.errors: list[str] = []
        self.csp = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        a = dict(attrs)
        if tag == "article":
            self.articles += 1
            self.scenarios.append(a.get("data-scenario"))
            self.ids.append(a.get("id"))
        if tag in FORBIDDEN:
            self.errors.append(f"Forbidden element <{tag}>")
        if any(key.startswith("on") or key in URL_ATTRIBUTES for key in a):
            self.errors.append(f"Executable/link attribute on <{tag}>")
        if tag == "meta" and a.get("http-equiv", "").lower() == "content-security-policy":
            self.csp = a.get("content", "").find("default-src 'none'") >= 0


def audit(html: str, *, require_six: bool = True) -> dict:
    if len(html.encode("utf-8")) > 3_000_000:
        raise ValueError("Public HTML exceeds 3MB limit")
    if DANGEROUS.search(html):
        raise ValueError("Potential secret, template token or private endpoint")
    parser = AuditParser()
    parser.feed(html)
    parser.close()
    if parser.errors:
        raise ValueError("; ".join(parser.errors))
    if not parser.csp:
        raise ValueError("Missing restrictive inline CSP")
    if require_six and (
        parser.articles != len(CASES)
        or set(parser.scenarios) != CASES
        or None in parser.ids
        or len(set(parser.ids)) != len(CASES)
    ):
        raise ValueError("Exactly one uniquely identified curated record per scenario required")
    return {"status": "STATIC_REVIEW_PASSED_HUMAN_APPROVAL_REQUIRED", "cases": parser.articles}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--html", type=Path, required=True)
    p.add_argument(
        "--allow-empty",
        action="store_true",
        help="Dry-run only: do not treat an empty site as release-ready",
    )
    a = p.parse_args()
    html = a.html.read_text(encoding="utf-8")
    print(audit(html, require_six=not a.allow_empty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
