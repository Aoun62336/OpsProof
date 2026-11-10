# OpsProof: M5-aware M6 + M7 source integration

**Source basis:** User-supplied `OpsProof_M5_Final_Source.zip` (9 November 2026), not the obsolete `OpsProof(3).zip` or previous M6/M7 staged ZIP.

**Delivery status: source-integrated and targeted offline-tested; M6/M7 NOT runtime-accepted.** Do not represent this as a production release, completed fault-verification milestone or validated AWS deployment.

## What changed

- Preserved 227 of the 234 latest M5 source files byte-for-byte. Made exactly seven explicit edits to three demo Python files and four Helm files for opt-in downstream behavior and immutable digest support. All M5 Kubernetes recovery, Rollouts, GitOps, UI, CI and docs source paths remain unchanged.
- Added the 72 M6/M7 source files previously staged, plus an additional M5-preservation source-contract test.
- Added a Terraform-managed one-day EKS CloudWatch log group for bounded log retention and destruction with the temporary stack.
- Added an explicit Helm input restriction for the M6 downstream fixture: demo-only and 0..2000 ms integer delay; disabled by default.
- Updated M6/M7 delivery documentation and compatibility notes to reflect the newer M5 baseline.

## Actual validation

The build-container Python 3.13 test environment passed the targeted pure contract/source tests. The result does **not** validate the required Python 3.14 application interpreter, real Kubernetes, Terraform provider, Helm rendering, AWS, GitHub Actions, or six live faults. Read `M6_M7_M5_COMPATIBILITY.md` and the external validation report before trying to deploy.

## What the M5 evidence actually supports

The November 9 M5 report documents local success for M4 regression, cluster/resources, deployment/security/persistence, Gateway, GitOps, scaling, and restricted recovery. Progressive delivery records real healthy/faulty rollback evidence but still labels final correlation pending. The M5 archive provides a single successful capacity trial per fixed/HPA/KEDA mode; M6 requires a larger repeated data set. Existing M5 evidence must be retained, never re-labeled as a newly executed M6 experiment.

## Next steps on Windows 11 (Git Bash)

1. Extract this archive into a separate, temporary comparison directory, **not on top of the accepted M5 checkout**.
2. Compare the seven changed files against your current source, review the new additions, then bring approved changes into a clean feature branch. Do not drop uncommitted M5 work.
3. With Python 3.14 + locked project dependencies available, run:

   ```bash
   export PYTHONPATH="$PWD/apps/control-plane/src:$PWD/apps/demo-workload/src:$PWD"
   uv run --project apps/control-plane --locked pytest scripts/m6/tests -q
   uv run --project apps/demo-workload --locked pytest apps/demo-workload/tests -q
   uv run --project apps/control-plane --locked pytest apps/control-plane/tests -q
   python -m pytest scripts/m5/tests -q
   python -m unittest discover -s scripts/m7/tests -v
   ```

4. Run Python Ruff/format checks and frontend `npm ci && npm run lint && npm run test && npm run build` in `apps/web`.
5. With real Helm/Terraform tooling, render both disabled and enabled M6 test-only chart profiles, verify resource admission/security, and run `terraform -chdir=infra/terraform fmt -check -recursive`, `terraform ... init -backend=false`, and `terraform ... validate`. Native validation has **not** yet been run on this delivery.
6. Verify all M5 local acceptance contracts after merging before performing an approved M6 test. Use **only** the isolated local k3d kubeconfig/context. M6's six live faults, durable trial orchestration, performance repetition, second workload proof and real AI qualification are still incomplete.
7. Follow the `docs/cloud/` runbooks for cost estimation and account identity. `enable_paid_resources=false` must remain the default. Terraform apply, GHCR publication, paid-model requests, GitHub push and EKS provisioning are separate explicit approvals.

## No secret or cloud side effects

The ZIP deliberately excludes `.git`, `.runtime`, `.env`, private kubeconfigs, local caches, tokens and dependencies. No cloud resources were provisioned; no publication occurred. A static scan is NOT proof that every possible embedded secret is absent, so review the source before external publication.

## Known M6/M7 acceptance gaps

- Full durable persisted scenario controller, six real fault adapters and independent postcondition/cleanup gates.
- At least three comparable passing capacity runs per mode with failed trials retained and actual k6 reconciliation.
- Held-out real-model diagnosis qualification, second-workload live proof, observed optimization and FinOps.
- Python 3.14 application regression, native Helm and Terraform validation, hosted CI/GHCR, full operator UI and accessible public replay audit.
- Explicitly approved temporary EKS deployment and independent cleanup, or a documented cost-gate blocker.

Source integration is not milestone completion. The validation report distinguishes `PASS`, `NOT RUN` and `BLOCKED` accurately.
