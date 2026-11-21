# Reliability verification runbook

Updated 15 November 2026. The [acceptance report](../history/m6-acceptance-report-2026-11-14.md) and [matrix](../history/m6-acceptance-matrix-2026-11-14.md) identify the executed results and remaining reviews.

## Toolchain and source checks

Use Python 3.14.10 for both locked applications, uv, the repository's Node/npm toolchain, Helm, kubectl, k3d and k6. The host chart-inspection helper uses Python 3.12 with PyYAML. The existing local cluster and private environment configuration are prerequisites for live checks.

Run these commands from the repository root in Windows Git Bash. Each source validator invocation creates a unique evidence directory.

```bash
uv sync --project apps/control-plane --locked
uv sync --project apps/demo-workload --locked
npm.cmd --prefix apps/web ci
python -m scripts.reliability.validate_source
```

The source validator runs Python lint/format/regressions, frontend lint/tests/build, 25 Helm profiles, k6 syntax, whitespace and the pinned source secret scanner. SQL tests require the separate real database validation below. In managed Windows sessions, an explicit writable `UV_CACHE_DIR` can be set for uv's cache.

The final implementation was also verified from a fresh detached Git worktree. Both Python environments and npm dependencies were installed from their locks using cached packages. The saved import provenance points into that worktree. Its commands, outputs and source hashes are in the reproduction evidence.

## Real SQL and isolated browser validation

```bash
uv run --project apps/control-plane --locked python scripts/reliability/validate_postgres.py --browser
```

This command requires local Docker access and creates an owned disposable PostgreSQL 18 container on localhost port 15432. It migrates through the preserved M5 schema, inserts preservation data, applies 0006/0007 and runs 27 SQL tests. The browser option exercises a real isolated API/database using the existing frontend. The harness removes its container and stops its servers. A passing result includes migration, preserved rows, integration, browser and cleanup checks.

The final M6 application/migration bytes match the retained passing PostgreSQL run. Subsequent host-runner and documentation commits are identified separately in the verification index.

## Local deployment and resource profile

```bash
python -m scripts.reliability.start_local
```

Startup uses the existing k3d cluster and explicit `.runtime/platform/kubeconfig.yaml` context `k3d-opsproof`. It checks the existing 5 GiB host RAM, 5 GiB Docker capacity and 15 GiB disk floors and preserves PVC identities. It refreshes the reviewed private API endpoint peers when required.

Active trials require 2 GiB free host RAM and 15 GiB free disk, with the existing 1 GiB emergency stop. Live Kubernetes node identity, Ready status and at least 5 GiB node capacity establish the running cluster's capacity. The verified node exposes six CPUs and approximately 9.7 GiB memory. Active trials can use that API measurement when the desktop sandbox cannot open Docker's Windows pipe.

The verified deployment serves application/chart commit `093b7ae` with content matching the later delivery. Migration 0007, the owned nonowner runtime Secret and the separate trial coordinator are enabled locally. HTTP arming and AI are disabled in the local deployment. Reuse is enabled only during its bounded check and restored afterward. The deployment records contain actual images, Application parameters, Secret UID and database-role provenance.

The optional measurement profile pauses Grafana and the Argo CD UI server while controllers, collectors, data services and the OpsProof UI run. Every accepted capacity trial used that profile. Restore and verify both UIs after measurements.

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.ui_test_profile restore
```

## Bounded fault trials and reconciliation

Review [the local execution profile](local-trials.md) before dispatch. The CLI acknowledges a local fault experiment, verifies a healthy baseline and creates a new durable trial.

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.run_local_trial --scenario worker_saturation --acknowledge M6_LOCAL_FAULT_TRIAL
```

The fixed catalog also includes `faulty_release`, `database_connectivity`, `worker_failure`, `downstream_latency` and `misleading_evidence`. The worker-failure CLI uses exact Pod deletion. A short job can complete during shutdown, producing a failed hypothesis with verified cleanup. The passing hard-crash evidence used the owner's separately approved one-off container signal test. Its exact helper and target guards are retained with the local-review evidence.

Success requires an independent matching hypothesis and cleanup receipt. Missing hypothesis evidence can produce a failed trial after restoration. Unknown dispatch or restoration retains an indeterminate record. Cleanup reconciliation appends evidence and releases the reservation when restoration is independently established.

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.reconcile_local_trial --run-directory .runtime/reliability/trials/RETAINED_RUN_ID --acknowledge M6_RECONCILE_ONLY
```

Use the actual retained run directory. Reconciliation uses the original checkpoint and performs cleanup only. Inspect the original result, reconciliation result, independent receipt and access-cleanup record together.

## k6 and capacity measurements

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.run_k6_local --run-id m6-review-20261115-a1 --rate 2 --seconds 30 --duration-ms 250 --vus 4 --acknowledge M6_LOCAL_DURABLE_JOBS
```

Choose a fresh lowercase run ID matching the CLI contract. This profile submits exactly 60 bounded jobs and reconciles their durable outcomes. The recorded stop test injected a below-threshold memory reading, stopped an actual owned k6 process and checked both submitted jobs in PostgreSQL and Redis.

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.run_local_trial --scenario worker_saturation --capacity-mode fixed --acknowledge M6_LOCAL_FAULT_TRIAL
uv run --project apps/control-plane --locked python -m scripts.reliability.run_local_trial --scenario worker_saturation --capacity-mode hpa --acknowledge M6_LOCAL_FAULT_TRIAL
uv run --project apps/control-plane --locked python -m scripts.reliability.run_local_trial --scenario worker_saturation --capacity-mode keda --acknowledge M6_LOCAL_FAULT_TRIAL
```

Execute sequentially and collect at least three independently passing trials per mode under the same profile. The capacity protocol uses 60 jobs at 2,000 ms, a 120-second background target of 80 requests per second, bounded concurrency and nearest-rank percentiles. Actual served rates, failures, IDs, resource samples and scale transitions are retained. Failed attempts keep their original outcome. The analysis CLI accepts repeated `--trial MODE:PATH` arguments and requires all three modes with at least three valid equivalent trials.

## Additional verification and evidence review

The retained operator checks deploy the existing reuse Helm contract, collect actual normal/delayed/recovered investigations, verify unsupported targeting and remove the owned resources. The image comparison uses preserved M5 and current M6 images with the same read-only protocol and limits. The deployed browser check covers authentication, CSRF, actual trial evidence, desktop/mobile navigation, accessibility and session revocation.

Deterministic synthetic diagnosis uses the versioned dataset. The completed provider comparison uses six reviewed real incidents and two derived abstention variants. Independent agents authored/reviewed the labels and assessed every returned prediction. Both external models failed qualification and remain disabled. AWS provisioning belongs to M7 under the original scope.

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.qualify --provider deterministic --output .runtime/reliability/acceptance/NEW_DETERMINISTIC_RESULT.json
```

The provider records are retained under `.runtime/reliability/acceptance/provider-qualification/free-cad3b3a65882404894e07ced84e177ac/`. Preserve the original Gemini HTTP 404, its seven unrun cases, the prospective compatibility amendment and the current comparator's HTTP 503. Seventeen inference attempts and one necessary metadata GET were issued. There were zero automatic retries. These are completed evidence records. A rerun requires a separately bounded operator evaluation and free-tier billing confirmation.

The verification index links all selected results, failed attempts, source/image identities, independent reviews, final platform state and archive hashes. Verify the SHA-256 manifests before review or sharing. Environment files, kubeconfigs, temporary credentials, browser traces and caches have private classification. The reviews are separate AI-agent assessments. External human certification remains a separate form of assurance.
