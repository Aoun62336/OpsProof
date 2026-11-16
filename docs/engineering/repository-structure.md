# Repository structure and compatibility

The control plane, demonstration workload and web console remain independently deployed applications. Local tooling is organized by responsibility.

- `scripts/platform/` owns local cluster bootstrap, Helm, GitOps, gateway and platform verification.
- `scripts/reliability/` owns bounded trials, independent verification, evidence, capacity analysis, source/image checks and illustrative cost modeling.
- `scripts/cloud/` owns pre-cloud infrastructure/release preparation, credential bootstrap, native validation, read-only inventory and sanitized replay. AWS acceptance remains separate.
- Application tests stay with their applications. Tool tests stay beside their owning package and use behavior-based filenames.
- `docs/operations/` contains maintained procedures. `docs/history/` contains dated acceptance and integration records. Historical commands refer to their recorded revisions.

No service, framework, runtime dependency or deployment architecture was added during standardization. Identical shutdown modules remain in each independently built Python application so their images do not depend on sibling source trees. Empty package markers and matching Python version pins are intentional. Compose overlays represent separate opt-in recovery, telemetry and integration responsibilities.

## Compatibility boundaries

Existing `/api/v1/m6` endpoints, `OPSPROOF_*_M6_*` settings, Helm `m6` values, migration revision IDs, SQL object names, image identities and `.runtime/m5` / `.runtime/m6` evidence paths remain compatibility contracts. Renaming them would invalidate stored evidence or change running-cluster configuration. Active Python modules, tests, UI symbols and workflows use responsibility names. AI remains disabled.

Source identity includes filenames. Previous source manifests and deployed image receipts describe the previous revision. They are retained as historical evidence, never relabeled as verification of this reorganization.

## Relocated files

The older partial platform source validator was consolidated into `python -m scripts.reliability.validate_source`. Other tracked relocations are below.

| Previous path | Maintained path |
|---|---|
| `.github/workflows/m5-foundation.yml` | `.github/workflows/platform.yml` |
| `.github/workflows/m6-verification-source.yml` | `.github/workflows/reliability.yml` |
| `.github/workflows/m7-release-ghcr.yml` | `.github/workflows/release.yml` |
| `.github/workflows/m7-supply-chain.yml` | `.github/workflows/security.yml` |
| `M6_M7_DELIVERY_README.md` | `docs/history/source-integration.md` |
| `apps/control-plane/src/opsproof_control/m6_access.py` | `apps/control-plane/src/opsproof_control/trial_access.py` |
| `apps/control-plane/src/opsproof_control/m6_catalog.py` | `apps/control-plane/src/opsproof_control/trial_catalog.py` |
| `apps/control-plane/src/opsproof_control/m6_diagnosis.py` | `apps/control-plane/src/opsproof_control/reliability_diagnosis.py` |
| `apps/control-plane/src/opsproof_control/m6_reuse.py` | `apps/control-plane/src/opsproof_control/workload_reuse.py` |
| `apps/control-plane/src/opsproof_control/m6_trial_api.py` | `apps/control-plane/src/opsproof_control/trial_api.py` |
| `apps/control-plane/src/opsproof_control/m6_trial_state.py` | `apps/control-plane/src/opsproof_control/trial_state.py` |
| `apps/control-plane/src/opsproof_control/m6_trial_store.py` | `apps/control-plane/src/opsproof_control/trial_store.py` |
| `apps/control-plane/src/opsproof_control/m6_trial_worker.py` | `apps/control-plane/src/opsproof_control/trial_worker.py` |
| `apps/control-plane/src/opsproof_control/m6_verification.py` | `apps/control-plane/src/opsproof_control/trial_verification.py` |
| `apps/control-plane/tests/test_m6_catalog.py` | `apps/control-plane/tests/test_catalog.py` |
| `apps/control-plane/tests/test_m6_database_permissions.py` | `apps/control-plane/tests/test_database_permissions.py` |
| `apps/control-plane/tests/test_m6_postgres_api.py` | `apps/control-plane/tests/test_postgres_api.py` |
| `apps/control-plane/tests/test_m6_postgres_safety.py` | `apps/control-plane/tests/test_postgres_safety.py` |
| `apps/control-plane/tests/test_m6_reuse.py` | `apps/control-plane/tests/test_reuse.py` |
| `apps/control-plane/tests/test_m6_trial_api.py` | `apps/control-plane/tests/test_trial_api.py` |
| `apps/control-plane/tests/test_m6_trial_postgres_integration.py` | `apps/control-plane/tests/test_trial_postgres_integration.py` |
| `apps/control-plane/tests/test_m6_trial_schema.py` | `apps/control-plane/tests/test_trial_schema.py` |
| `apps/control-plane/tests/test_m6_trial_store.py` | `apps/control-plane/tests/test_trial_store.py` |
| `apps/control-plane/tests/test_m6_verification_postgres.py` | `apps/control-plane/tests/test_verification_postgres.py` |
| `apps/demo-workload/src/opsproof_demo/m6_probe.py` | `apps/demo-workload/src/opsproof_demo/dependency_probe.py` |
| `apps/demo-workload/tests/test_m6_probe.py` | `apps/demo-workload/tests/test_dependency_probe.py` |
| `apps/web/e2e/m6-trials.spec.ts` | `apps/web/e2e/trials.spec.ts` |
| `apps/web/src/pages/M6TrialsPage.test.tsx` | `apps/web/src/pages/TrialsPage.test.tsx` |
| `apps/web/src/pages/M6TrialsPage.tsx` | `apps/web/src/pages/TrialsPage.tsx` |
| `docs/ENGINEERING_LOG.md` | `docs/history/engineering-log.md` |
| `docs/architecture/UI_DESIGN.md` | `docs/architecture/ui-design.md` |
| `docs/cloud/COST_ESTIMATE.example.json` | `docs/cloud/cost-estimate.example.json` |
| `docs/cloud/M7_AWS_IDENTITY_AND_COST_SETUP.md` | `docs/cloud/identity-and-cost.md` |
| `docs/cloud/M7_CLOUD_VERIFICATION_AND_TEARDOWN.md` | `docs/cloud/verification-and-teardown.md` |
| `docs/cloud/M7_GITHUB_OIDC_GHCR_RELEASE.md` | `docs/cloud/release.md` |
| `docs/cloud/M7_TERRAFORM_OPERATIONS.md` | `docs/cloud/terraform-operations.md` |
| `docs/engineering/M6_EXECUTION_PLAN_2026-11-14.md` | `docs/history/m6-execution-plan-2026-11-14.md` |
| `docs/engineering/M6_M7_INTEGRATION_STATUS.md` | `docs/history/m6-m7-integration-status.md` |
| `docs/engineering/M6_M7_M5_COMPATIBILITY.md` | `docs/history/m6-m7-m5-compatibility.md` |
| `docs/engineering/M6_TRIAL_LEDGER_IMPLEMENTATION_2026-11-10.md` | `docs/history/m6-trial-ledger-implementation-2026-11-10.md` |
| `docs/experiments/M6_ACCEPTANCE_MATRIX_2026-11-14.md` | `docs/history/m6-acceptance-matrix-2026-11-14.md` |
| `docs/experiments/M6_ACCEPTANCE_REPORT_2026-11-14.md` | `docs/history/m6-acceptance-report-2026-11-14.md` |
| `docs/experiments/M6_ENGINEERING_DETAILS.md` | `docs/engineering/reliability-design.md` |
| `docs/experiments/M6_FULL_SYSTEM_VERIFICATION.md` | `docs/history/m6-full-system-verification.md` |
| `docs/experiments/M6_LOCAL_EXECUTION_PROFILE.md` | `docs/operations/local-trials.md` |
| `docs/experiments/M6_SCENARIO_CATALOG.md` | `docs/operations/scenario-catalog.md` |
| `docs/experiments/M6_SOURCE_STATUS_2026-11-08.md` | `docs/history/m6-source-status-2026-11-08.md` |
| `docs/experiments/M6_VERIFICATION_RUNBOOK_2026-11-14.md` | `docs/operations/reliability-verification.md` |
| `docs/operations/M4_ACCEPTANCE_CLOSURE_2026-11-07.md` | `docs/history/m4-acceptance-closure-2026-11-07.md` |
| `docs/operations/M4_INVESTIGATION_RECOVERY.md` | `docs/operations/investigation-and-recovery.md` |
| `docs/operations/M4_LOCAL_VALIDATION_REPORT.md` | `docs/history/m4-local-validation-report.md` |
| `docs/operations/M4_SHUTDOWN_EVIDENCE.json` | `docs/history/m4-shutdown-evidence.json` |
| `docs/operations/M4_TRIAL_RESULTS.md` | `docs/history/m4-trial-results.md` |
| `docs/operations/M5_ACCEPTANCE_REPORT_2026-11-07.md` | `docs/history/m5-acceptance-report-2026-11-07.md` |
| `docs/operations/M5_ACCEPTANCE_REPORT_2026-11-08.md` | `docs/history/m5-acceptance-report-2026-11-08.md` |
| `docs/operations/M5_ACCEPTANCE_REPORT_2026-11-09.md` | `docs/history/m5-acceptance-report-2026-11-09.md` |
| `docs/operations/M5_GATEWAY_FOUNDATION.md` | `docs/operations/gateway.md` |
| `docs/operations/M5_GITOPS_PROTOCOL.md` | `docs/operations/gitops.md` |
| `docs/operations/M5_K3D_HELM_FOUNDATION.md` | `docs/operations/local-platform.md` |
| `docs/operations/M5_LOCAL_RUNBOOK.md` | `docs/operations/local-runbook.md` |
| `docs/operations/M5_STAGE4_TO_7_ACCEPTANCE_CONTRACT.md` | `docs/history/m5-stage4-to-7-acceptance-contract.md` |
| `docs/operations/M6_WORKSPACE_UI_AND_OFFLINE_EVIDENCE_2026-11-15.md` | `docs/history/m6-workspace-ui-and-offline-evidence-2026-11-15.md` |
| `docs/operations/OBSERVABILITY_VERIFICATION.md` | `docs/operations/observability-verification.md` |
| `docs/operations/WORKER_SHUTDOWN.md` | `docs/operations/worker-shutdown.md` |
| `scripts/m5/__init__.py` | `scripts/platform/__init__.py` |
| `scripts/m5/adopt_gitops.py` | `scripts/platform/adopt_gitops.py` |
| `scripts/m5/bootstrap.py` | `scripts/platform/bootstrap.py` |
| `scripts/m5/build_release_images.py` | `scripts/platform/build_release_images.py` |
| `scripts/m5/capacity_load.py` | `scripts/platform/capacity_load.py` |
| `scripts/m5/deploy_foundation.py` | `scripts/platform/deploy_foundation.py` |
| `scripts/m5/deploy_gateway.py` | `scripts/platform/deploy_gateway.py` |
| `scripts/m5/deploy_observability.py` | `scripts/platform/deploy_observability.py` |
| `scripts/m5/enable_recovery.py` | `scripts/platform/enable_recovery.py` |
| `scripts/m5/forward.py` | `scripts/platform/forward.py` |
| `scripts/m5/gitops_config.py` | `scripts/platform/gitops_config.py` |
| `scripts/m5/install_argocd.py` | `scripts/platform/install_argocd.py` |
| `scripts/m5/install_rollouts.py` | `scripts/platform/install_rollouts.py` |
| `scripts/m5/local_cluster.py` | `scripts/platform/local_cluster.py` |
| `scripts/m5/preflight.py` | `scripts/platform/preflight.py` |
| `scripts/m5/render_gitops.py` | `scripts/platform/render_gitops.py` |
| `scripts/m5/render_local_secrets.py` | `scripts/platform/render_local_secrets.py` |
| `scripts/m5/security_checks.py` | `scripts/platform/security_checks.py` |
| `scripts/m5/serve_local_git.py` | `scripts/platform/serve_local_git.py` |
| `scripts/m5/smoke.py` | `scripts/platform/smoke.py` |
| `scripts/m5/tests/test_foundation.py` | `scripts/platform/tests/test_foundation.py` |
| `scripts/m5/tests/test_kubernetes_route_registration.py` | `scripts/platform/tests/test_kubernetes_route_registration.py` |
| `scripts/m5/tests/test_render_local_secrets.py` | `scripts/platform/tests/test_render_local_secrets.py` |
| `scripts/m5/tests/test_smoke.py` | `scripts/platform/tests/test_smoke.py` |
| `scripts/m5/validate_charts.py` | `scripts/platform/validate_charts.py` |
| `scripts/m5/validate_gateway.py` | `scripts/platform/validate_gateway.py` |
| `scripts/m5/verify_bootstrap_cleanup.py` | `scripts/platform/verify_bootstrap_cleanup.py` |
| `scripts/m5/verify_consumer_recovery.py` | `scripts/platform/verify_consumer_recovery.py` |
| `scripts/m5/verify_gateway.py` | `scripts/platform/verify_gateway.py` |
| `scripts/m5/verify_gitops.py` | `scripts/platform/verify_gitops.py` |
| `scripts/m5/verify_k3d.py` | `scripts/platform/verify_k3d.py` |
| `scripts/m5/verify_observability.py` | `scripts/platform/verify_observability.py` |
| `scripts/m5/verify_persistence.py` | `scripts/platform/verify_persistence.py` |
| `scripts/m5/verify_recovery.py` | `scripts/platform/verify_recovery.py` |
| `scripts/m5/verify_recovery_security.py` | `scripts/platform/verify_recovery_security.py` |
| `scripts/m5/verify_release_incident.py` | `scripts/platform/verify_release_incident.py` |
| `scripts/m5/verify_rollouts.py` | `scripts/platform/verify_rollouts.py` |
| `scripts/m5/verify_scaling.py` | `scripts/platform/verify_scaling.py` |
| `scripts/m5/verify_security.py` | `scripts/platform/verify_security.py` |
| `scripts/m6/__init__.py` | `scripts/reliability/__init__.py` |
| `scripts/m6/acceptance_audit.py` | `scripts/reliability/acceptance_audit.py` |
| `scripts/m6/admission_boundary.py` | `scripts/reliability/admission_boundary.py` |
| `scripts/m6/analyze_capacity.py` | `scripts/reliability/analyze_capacity.py` |
| `scripts/m6/build_images_local.py` | `scripts/reliability/build_images_local.py` |
| `scripts/m6/capacity_adapter.py` | `scripts/reliability/capacity_adapter.py` |
| `scripts/m6/capacity_load.py` | `scripts/reliability/capacity_load.py` |
| `scripts/m6/collect_queue_state.py` | `scripts/reliability/collect_queue_state.py` |
| `scripts/m6/contracts.py` | `scripts/reliability/contracts.py` |
| `scripts/m6/data_access.py` | `scripts/reliability/data_access.py` |
| `scripts/m6/evidence_manifest.py` | `scripts/reliability/evidence_manifest.py` |
| `scripts/m6/fetch_pricing.py` | `scripts/reliability/fetch_pricing.py` |
| `scripts/m6/finops_model.py` | `scripts/reliability/finops_model.py` |
| `scripts/m6/independent_hypothesis.py` | `scripts/reliability/independent_hypothesis.py` |
| `scripts/m6/inspect_image_runtime.py` | `scripts/reliability/inspect_image_runtime.py` |
| `scripts/m6/inspect_reuse.py` | `scripts/reliability/inspect_reuse.py` |
| `scripts/m6/live_observer.py` | `scripts/reliability/live_observer.py` |
| `scripts/m6/local_environment.py` | `scripts/reliability/local_environment.py` |
| `scripts/m6/observe_local_trial.py` | `scripts/reliability/observe_local_trial.py` |
| `scripts/m6/preflight.py` | `scripts/reliability/preflight.py` |
| `scripts/m6/prepare_runtime_access.py` | `scripts/reliability/prepare_runtime_access.py` |
| `scripts/m6/process_identity.py` | `scripts/reliability/process_identity.py` |
| `scripts/m6/qualify.py` | `scripts/reliability/qualify.py` |
| `scripts/m6/reconcile_jobs.py` | `scripts/reliability/reconcile_jobs.py` |
| `scripts/m6/reconcile_local_trial.py` | `scripts/reliability/reconcile_local_trial.py` |
| `scripts/m6/refresh_api_allowlists.py` | `scripts/reliability/refresh_api_allowlists.py` |
| `scripts/m6/restricted_access.py` | `scripts/reliability/restricted_access.py` |
| `scripts/m6/run_k6_local.py` | `scripts/reliability/run_k6_local.py` |
| `scripts/m6/run_local_trial.py` | `scripts/reliability/run_local_trial.py` |
| `scripts/m6/scan_images.py` | `scripts/reliability/scan_images.py` |
| `scripts/m6/scenario_adapters.py` | `scripts/reliability/scenario_adapters.py` |
| `scripts/m6/smoke_images.py` | `scripts/reliability/smoke_images.py` |
| `scripts/m6/start_local.py` | `scripts/reliability/start_local.py` |
| `scripts/m6/tests/__init__.py` | `scripts/reliability/tests/__init__.py` |
| `scripts/m6/tests/test_m5_aware_integration.py` | `scripts/reliability/tests/test_platform_compatibility.py` |
| `scripts/m6/tests/test_m6_acceptance_audit.py` | `scripts/reliability/tests/test_acceptance_audit.py` |
| `scripts/m6/tests/test_m6_adapters.py` | `scripts/reliability/tests/test_adapters.py` |
| `scripts/m6/tests/test_m6_api_allowlists.py` | `scripts/reliability/tests/test_api_allowlists.py` |
| `scripts/m6/tests/test_m6_cleanup_outcomes.py` | `scripts/reliability/tests/test_cleanup_outcomes.py` |
| `scripts/m6/tests/test_m6_collect.py` | `scripts/reliability/tests/test_collect.py` |
| `scripts/m6/tests/test_m6_contracts.py` | `scripts/reliability/tests/test_contracts.py` |
| `scripts/m6/tests/test_m6_diagnosis.py` | `scripts/reliability/tests/test_diagnosis.py` |
| `scripts/m6/tests/test_m6_finops.py` | `scripts/reliability/tests/test_finops.py` |
| `scripts/m6/tests/test_m6_independent_hypothesis.py` | `scripts/reliability/tests/test_independent_hypothesis.py` |
| `scripts/m6/tests/test_m6_measurements.py` | `scripts/reliability/tests/test_measurements.py` |
| `scripts/m6/tests/test_m6_qualification.py` | `scripts/reliability/tests/test_qualification.py` |
| `scripts/m6/tests/test_m6_runner_safety.py` | `scripts/reliability/tests/test_runner_safety.py` |
| `scripts/m6/tests/test_m6_runtime_regressions.py` | `scripts/reliability/tests/test_runtime_regressions.py` |
| `scripts/m6/tests/test_m6_trial_state.py` | `scripts/reliability/tests/test_trial_state.py` |
| `scripts/m6/trial_evidence.py` | `scripts/reliability/trial_evidence.py` |
| `scripts/m6/ui_test_profile.py` | `scripts/reliability/ui_test_profile.py` |
| `scripts/m6/validate_admission.py` | `scripts/reliability/validate_admission.py` |
| `scripts/m6/validate_charts.py` | `scripts/reliability/validate_charts.py` |
| `scripts/m6/validate_postgres.py` | `scripts/reliability/validate_postgres.py` |
| `scripts/m6/validate_source.py` | `scripts/reliability/validate_source.py` |
| `scripts/m6/verify_local_trial.py` | `scripts/reliability/verify_local_trial.py` |
| `scripts/m6/verify_scenarios.py` | `scripts/reliability/verify_scenarios.py` |
| `scripts/m7/__init__.py` | `scripts/cloud/__init__.py` |
| `scripts/m7/aws_readonly_inventory.py` | `scripts/cloud/aws_readonly_inventory.py` |
| `scripts/m7/build_public_replay.py` | `scripts/cloud/build_public_replay.py` |
| `scripts/m7/cost_gate.py` | `scripts/cloud/cost_envelope.py` (subsequently consolidated) |
| `scripts/m7/tests/__init__.py` | `scripts/cloud/tests/__init__.py` |
| `scripts/m7/tests/test_cost_gate.py` | `scripts/cloud/tests/test_domainless.py` (cost regressions consolidated) |
| `scripts/m7/tests/test_inventory.py` | `scripts/cloud/tests/test_inventory.py` |
| `scripts/m7/tests/test_public_replay.py` | `scripts/cloud/tests/test_public_replay.py` |
| `scripts/verify_m4_security.py` | `scripts/verify_authentication.py` |
| `scripts/verify_milestone4.py` | `scripts/verify_recovery.py` |
