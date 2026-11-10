"""Build strictly static, operator-reviewed OpsProof evidence replay.

No raw logs, sessions or live API wiring. Refuses suspicious input before writing
any public file. Human review of chosen evidence still remains mandatory.
"""
import argparse
import hashlib
import html
import json
import re
from pathlib import Path

CASES = frozenset({
    "worker_saturation", "faulty_release", "database_connectivity",
    "worker_failure", "downstream_latency", "misleading_evidence",
})
FIELDS = frozenset({"id", "scenario", "title", "environment", "source_commit",
                    "status", "observed_utc", "summary", "findings", "limitations",
                    "source_evidence_sha256"})
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
    if not re.fullmatch(r"[a-f0-9]{64}", obj["source_evidence_sha256"]):
        raise ValueError("Require actual evidence SHA256, not a title")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,79}", obj["id"]):
        raise ValueError("Invalid public case identifier")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", obj["observed_utc"]):
        raise ValueError("Require UTC timestamp")
    for key, size in (("title", 90), ("summary", 900), ("limitations", 900)):
        text(obj[key], size)
    if not isinstance(obj["findings"], list) or not 1 <= len(obj["findings"]) <= 12:
        raise ValueError("One to twelve curated observations required")
    for finding in obj["findings"]:
        text(finding, 400)
    return obj


def build(cases: list[dict]) -> str:
    if not isinstance(cases, list) or len(cases) > 24:
        raise ValueError("Expected a bounded set of curated evidence cases")
    ids = set()
    sections = []
    for case in cases:
        case = validate_case(case)
        if case["id"] in ids:
            raise ValueError("Duplicate evidence case identifier")
        ids.add(case["id"])
        e = lambda value: html.escape(str(value), quote=True)
        findings = "".join(f"<li>{e(line)}</li>" for line in case["findings"])
        sections.append(f"""<article class="case" id="{e(case['id'])}">
  <div class="case-top"><span class="kicker">{e(case['scenario'].replace('_',' '))}</span><span class="status">{e(case['status'])}</span></div>
  <h2>{e(case['title'])}</h2><p class="summary">{e(case['summary'])}</p>
  <dl><div><dt>Environment</dt><dd>{e(case['environment'])}</dd></div>
  <div><dt>Recorded UTC</dt><dd>{e(case['observed_utc'])}</dd></div>
  <div><dt>Source revision</dt><dd><code>{e(case['source_commit'])[:12]}</code></dd></div>
  <div><dt>Evidence SHA-256</dt><dd><code>{e(case['source_evidence_sha256'])}</code></dd></div></dl>
  <details><summary>Observations and limitations</summary><h3>Observations</h3><ul>{findings}</ul>
  <h3>Limitations</h3><p>{e(case['limitations'])}</p></details>
</article>""")
    main = "\n".join(sections) if sections else '<p class="empty">No curated evidence has been approved for publication. This is not a successful experiment report.</p>'
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OpsProof | Verified evidence replay</title><meta name="robots" content="noindex"/>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"/>
<style>
:root{color-scheme:light;--canvas:#f7f7f2;--surface:#fff;--ink:#1b2b27;--muted:#52665e;--line:#d9e1da;--accent:#245b47}*{box-sizing:border-box}
body{margin:0;background:var(--canvas);color:var(--ink);font:16px/1.65 system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}
main{max-width:1060px;margin:auto;padding:48px 24px 100px}header{border-bottom:1px solid var(--line);padding-bottom:28px;margin-bottom:32px}
.eyebrow,.kicker{text-transform:uppercase;letter-spacing:.12em;color:var(--accent);font-size:.76rem;font-weight:700}
h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.12;letter-spacing:-.035em;margin:.5rem 0}header p{max-width:730px;color:var(--muted)}
.case{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:26px;margin:20px 0;box-shadow:0 4px 16px #122c1c0a}
.case-top{display:flex;gap:16px;justify-content:space-between;flex-wrap:wrap}.status{border:1px solid var(--line);border-radius:20px;padding:2px 12px;font-size:.8rem}
h2{font-size:1.5rem;line-height:1.2;margin:.8rem 0}h3{font-size:1rem}dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:24px 0}
dt{font-size:.76rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}dd{margin:3px 0;overflow-wrap:anywhere}code{font:12px/1.5 ui-monospace,monospace}
summary{cursor:pointer;color:var(--accent);font-weight:700}summary:focus-visible{outline:3px solid var(--accent);outline-offset:4px}
footer{padding:30px 0;border-top:1px solid var(--line);font-size:.87rem;color:var(--muted)}.empty{padding:30px;border:1px dashed var(--line)}
@media(max-width:600px){main{padding:28px 16px 60px}.case{padding:18px}dl{grid-template-columns:1fr}}
</style></head><body><main><header><div class="eyebrow">OpsProof / public evidence replay</div><h1>Observed incidents. Verifiable outcomes.</h1>
<p>Offline read-only publication of manually reviewed, sanitized experiment evidence. No operator access, live API connection, cloud endpoint or recovery controls. Individual cases show their environment and limitations.</p></header>
""" + main + """<footer>Independent engineering demonstration. Synthetic and temporary test observations are not production availability or customer-impact claims.</footer></main></body></html>"""


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
    rendered = build(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    digest = hashlib.sha256(rendered.encode()).hexdigest()
    print(f"Offline replay created ({len(data)} cases), SHA256={digest}. Manual review still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
