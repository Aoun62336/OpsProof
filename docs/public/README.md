# M7 public evidence source

Do not commit synthetic fixtures, raw production logs, Kubernetes Secrets or
operator API URLs. A reviewed, sanitized `m6-cases.json` must contain exactly six
real, independently verified M6 cases under the schema in
`scripts/cloud/build_public_replay.py`. The actual M6 file is intentionally **not
fabricated** because the final accepted M6 evidence has not been provided here.

The Pages workflow is blocked until a human reviews the case file, commits it to
`main`, calculates its SHA-256, configures GitHub Pages to use **GitHub Actions**,
and approves the protected `github-pages` environment deployment.

The pipeline automatically creates the static HTML from the reviewed JSON and
refuses any content rejected by the static sanitizer; these automated checks do
not replace a privacy review.
