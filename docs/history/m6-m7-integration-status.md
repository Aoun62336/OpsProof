> Historical record. Commands, paths and results below describe the recorded revision. See [the current repository guide](../../README.md) for maintained commands and status.

# M6/M7 integration status: M5-aware source merge (9 November 2026)

> Historical integration record. See the [14 November M6 acceptance report](m6-acceptance-report-2026-11-14.md)
> for the actual Python 3.14, PostgreSQL, Helm and browser results and current blockers.

**Authoritative input:** `OpsProof_M5_Final_Source.zip` supplied after the final November 9 M5 acceptance report, containing 234 source files. The original November 8 M6/M7 staged source is reference material only, never the source authority.

**What was integrated:** 72 proposed additions + one new compatibility contract test; only seven existing M5 files edited for optional downstream HTTP test profile and immutable image digest support. All other M5 files preserved byte-for-byte. The M6 downstream fixture is off by default, with fixed internal destination and bounded timeout/attempts. Terraform paid resources are off by default; GitHub release is workflow-dispatch and contains no AWS apply.

**Review findings:** The final M5 file differs from the old staged snapshot in 23 paths. Differences affecting recovery policies/client/worker, rollout Gateway routes, React Kubernetes page, tests and M5 scripts were intentionally preserved. The newest M5 report records completed local M5 gates but progressive-delivery correlation pending final review. No push/hosted CI has occurred.

**Offline tested:** 83 targeted pytest cases, including 17 M5 script contract tests and added source compatibility guards, plus 14 pytest subtests, passed in the container's Python 3.13 testing environment. This is distinct from the Python 3.14 target and previously reported local M5 runtime acceptance.

**Unverified:** Complete Python 3.14 dependency-locked regression and Ruff, native Helm renders, Terraform fmt/init/validate, Docker/k3d, real M6 fault orchestration and all six scenarios, nine repeated capacity trials, real AI and second-workload validation, actual hosted CI/release, AWS creation and teardown.

**M7 source limits:** Public replay generator is an offline static evidence presentation foundation, not a completed professional public-site UX. Terraform uses a temporary cost-guarded public-subnet single-node profile, **not production high availability**. A single EC2 node, IAM and network topology must be reviewed with actual cloud cost and target behavior. Current source includes one-day Terraform-managed EKS log retention. GitHub OIDC subject must be captured for this exact repository: new post-July-2026 repositories use immutable owner/repo IDs.

Never report `M6 complete` or `M7 complete` until the respective acceptance matrix is independently supported with runtime evidence and reviewed publication/teardown results.
