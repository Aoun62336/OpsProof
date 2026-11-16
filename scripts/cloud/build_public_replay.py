"""Build strictly static, operator-reviewed OpsProof evidence replay.

No raw logs, sessions or live API wiring. Refuses suspicious input before writing
any public file. Human review of chosen evidence still remains mandatory.
"""

import argparse
import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path

CASES = frozenset(
    {
        "worker_saturation",
        "faulty_release",
        "database_connectivity",
        "worker_failure",
        "downstream_latency",
        "misleading_evidence",
    }
)
FIELDS = frozenset(
    {
        "id",
        "scenario",
        "title",
        "environment",
        "source_commit",
        "source_tree_sha256",
        "source_dirty",
        "status",
        "observed_utc",
        "summary",
        "findings",
        "limitations",
        "source_evidence_sha256",
    }
)
SUSPICIOUS = re.compile(
    r"(?i)(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|-----BEGIN |"
    r"(?:password|token|api[_-]?key|authorization|set-cookie)\s*[:=]|"
    r"Bearer\s+[A-Za-z0-9._-]+|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b|"
    r"https?://(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[0-1])\.|127\.0\.0\.1))"
)


def text(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("Missing, empty or overlong evidence text")
    if SUSPICIOUS.search(value):
        raise ValueError("Potential secret, personal identifier or internal URL in public evidence")
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in value):
        raise ValueError("Control characters prohibited")
    return value.strip()


def validate_case(obj: dict) -> dict:
    if not isinstance(obj, dict) or set(obj) != FIELDS:
        raise ValueError("Evidence requires exact allowlisted schema; no raw log fields")
    if obj["scenario"] not in CASES:
        raise ValueError("Unknown scenario")
    if obj["environment"] not in ("local-compose", "local-k3d", "temporary-eks"):
        raise ValueError("Environment identity must be explicit")
    if obj["status"] not in ("succeeded", "failed", "aborted", "indeterminate", "blocked"):
        raise ValueError("Unsupported result status")
    if not re.fullmatch(r"[a-f0-9]{40}", obj["source_commit"]):
        raise ValueError("Require real source commit SHA1, no placeholder")
    if type(obj["source_dirty"]) is not bool:
        raise ValueError("Explicit clean/dirty source state required")
    if not isinstance(obj["source_tree_sha256"], str) or not re.fullmatch(
        r"[a-f0-9]{64}", obj["source_tree_sha256"]
    ):
        raise ValueError("Actual tested source tree SHA256 required")
    if not re.fullmatch(r"[a-f0-9]{64}", obj["source_evidence_sha256"]):
        raise ValueError("Require actual evidence SHA256, not a title")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,79}", obj["id"]):
        raise ValueError("Invalid public case identifier")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", obj["observed_utc"]):
        raise ValueError("Require UTC timestamp")
    datetime.fromisoformat(obj["observed_utc"])
    for key, size in (("title", 90), ("summary", 900), ("limitations", 900)):
        text(obj[key], size)
    if not isinstance(obj["findings"], list) or not 1 <= len(obj["findings"]) <= 12:
        raise ValueError("One to twelve curated observations required")
    for finding in obj["findings"]:
        text(finding, 400)
    return obj


def build(cases: list[dict], *, require_all: bool = False) -> str:
    if not isinstance(cases, list) or len(cases) > 24:
        raise ValueError("Expected a bounded set of curated evidence cases")
    if require_all and (
        len(cases) != len(CASES)
        or {x.get("scenario") for x in cases if isinstance(x, dict)} != CASES
    ):
        raise ValueError("Publication requires exactly one record for each of the six scenarios")
    ids = set()
    sections = []
    for case in cases:
        case = validate_case(case)
        if case["id"] in ids:
            raise ValueError("Duplicate evidence case identifier")
        ids.add(case["id"])

        def e(value):
            return html.escape(str(value), quote=True)

        findings = "".join(f"<li>{e(line)}</li>" for line in case["findings"])
        sections.append(f"""<article class="case"
 data-scenario="{e(case["scenario"])}" id="{e(case["id"])}">
  <div class="case-top">
  <span class="kicker">{e(case["scenario"].replace("_", " "))}</span>
  <span class="status">{e(case["status"])}</span></div>
  <h2>{e(case["title"])}</h2><p class="summary">{e(case["summary"])}</p>
  <dl><div><dt>Environment</dt><dd>{e(case["environment"])}</dd></div>
  <div><dt>Recorded UTC</dt><dd>{e(case["observed_utc"])}</dd></div>
  <div><dt>Source revision</dt><dd><code>{e(case["source_commit"])}</code></dd></div>
  <div><dt>Tested source tree</dt><dd><code>{e(case["source_tree_sha256"])}</code>
  ({"uncommitted changes included" if case["source_dirty"] else "clean checkout"})</dd></div>
  <div><dt>Evidence SHA-256</dt><dd><code>{e(case["source_evidence_sha256"])}</code></dd></div></dl>
  <details><summary>Observations and limitations</summary><h3>Observations</h3><ul>{findings}</ul>
  <h3>Limitations</h3><p>{e(case["limitations"])}</p></details>
</article>""")
    main = (
        "\n".join(sections)
        if sections
        else (
            '<p class="empty">No curated evidence has been approved for publication. '
            "This is not a successful experiment report.</p>"
        )
    )
    template = Path(__file__).with_name("templates") / "replay.html"
    return template.read_text(encoding="utf-8").replace("__OPSPROOF_CASES__", main)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curated-input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", choices=["I_REVIEWED_PUBLIC_EVIDENCE"], required=True)
    args = parser.parse_args()
    if args.output.suffix.lower() != ".html":
        parser.error("Output must be an HTML file")
    data = json.loads(args.curated_input.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        parser.error("Curated input must be a list")
    rendered = build(data, require_all=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    digest = hashlib.sha256(rendered.encode()).hexdigest()
    print(
        f"Offline replay created ({len(data)} cases), SHA256={digest}. "
        "Manual review still required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
