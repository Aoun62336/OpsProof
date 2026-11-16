# M6 workspace UI and offline evidence update

## Implemented UI

The Workloads, Deployments, Capacity and Runbooks pages use operational cards built from the existing Kubernetes observation and recovery APIs.

- Workloads presents requested and ready replicas, dependency state and workload details.
- Deployments presents the observed image, resource version, namespace and expandable workload identity.
- Capacity presents queued jobs, replicas and configured CPU and memory requests relative to limits. The page explicitly identifies the unavailable measured consumption.
- Runbooks presents the supported recovery, prerequisites, proposal form, separate approval, expiry countdown and recorded outcomes. Uncertain outcomes and server errors remain visible.
- Page breadcrumbs and navigation icons identify each section.

The existing colour tokens and typography are preserved. The forest sidebar, porcelain background, paper cards, bronze accent and existing status colours are reused. Original font families are Instrument Sans, Newsreader and IBM Plex Mono.

Resource observations become unknown after 15 seconds. Metric freshness uses the existing 30-second Kubernetes policy window. Missing, future and invalid timestamps also produce unknown state. Expired or unavailable recovery approvals are disabled. Cached records following retrieval errors carry unavailable state.

## Verification

- Frontend unit suite passed all 44 tests, including 31 resource-formatting, freshness and operational-page tests.
- Production TypeScript and Vite build passed.
- Browser validation used the new production assets with the live authenticated local control API.
- All four pages passed at widths of 1440, 1280, 768, 390 and 320 pixels. All 20 combinations preserved the original palette, avoided horizontal overflow and reported zero serious or critical Axe accessibility violations.
- Dark browser preference preserved the original light content palette.
- Browser fixtures verified stale observations, proposal payloads, CSRF header presence and explicit approval. These mutation fixtures were intercepted locally.
- Browser validation confirmed `ai_enabled=false` and recorded no browser errors.
- Source validation includes Python regressions, demo regressions, frontend lint/tests/build, Helm checks, k6 syntax, whitespace and secret scanning. SQL-dependent tests skip in this source-only run.

Browser receipts and desktop/mobile screenshots are saved under `.runtime/m6/acceptance/workspace-ui-04cf35d0a6fd43d1a381a7c6236af5f9/`. Source validation receipts are saved under `.runtime/m6/acceptance/source/`.

## Offline diagnosis evidence improvements

The M6 evaluation request builder now supplies explicit measurement units, replay-clock freshness, expected queue behaviour and existing signature thresholds. Production SLO values remain unavailable in these records. The numerical deterministic rules retain their previous behaviour.

Queue lag is identified as undelivered Redis Stream job messages. Duplicate job IDs can occur. Durable waiting-job counts remain separate recorded evidence. This prevents interpreting the queue count as elapsed time or assuming every message is a distinct durable job.

Model results pass JSON field-path resolution against the exact supplied facts. Missing paths and invalid indices raise a validation error. Supplied `null`, false and zero values remain valid references, including missing-collector evidence supporting abstention. Path existence checks leave interpretation and factual reasoning subject to review.

An offline audit of the saved original responses found one missing citation path in a Groq response. Seven saved Gemini predictions had existing paths. The remaining Gemini case had no accepted prediction. The original results and qualification dispositions are preserved.

## Held-out preparation

Four additional observations from three previously unused capacity trials were independently labeled by `/root/ground_truth_review`. Three labels are `worker_saturation` and one is `unknown` with abstention. Every persisted canonical fact hash matches the independent review.

The model-visible facts, private labels/provenance, protocol, deterministic result and SHA-256 manifest are versioned under `benchmarks/ai/capacity_held_out_v1/`. Model-visible cases contain only an opaque ID and facts. The private review records source trials and reconstruction limits.

The deterministic replay matched all four labels. The original eight cases remain unchanged and retain their previous deterministic result of five correct. The new cases supply narrow retrospective capacity coverage. Two observations share one KEDA trial. They support no six-scenario or prospective accuracy claim.

AI candidate evaluation status is `NOT_RUN_OFFLINE_PREPARATION_ONLY`. Comparing model candidates on the new cases remains deferred under the owner's instruction to keep AI disabled. Future comparison must use identical frozen augmented inputs and keep private labels outside model requests.

The read-only offline audit is saved at `.runtime/m6/acceptance/offline-evidence-improvements-2026-11-15.json`.

## Deployment status

The approved web image was built and imported from the owner's Docker-authorized terminal after the initial execution policy denied Docker engine access. The deployed image is `opsproof-web:m6-ec2b9255c6d34f3b`, identified by web build-context SHA-256 `ec2b9255c6d34f3b9cf7043b7d1a47fce452fab0271266de4407645541e0ea40`.

The existing Argo CD web application's image parameters were updated with identity and resource-version checks. Argo CD reached `Synced` and `Healthy`, with one ready updated web replica. All 34 HTTP-served production assets matched the approved local build by SHA-256. The Kubernetes-hosted pages passed all 20 page/viewport browser checks, including original palette preservation and zero serious or critical accessibility findings. AI remained disabled.

Deployment receipts, served-asset hashes, browser results and screenshots are saved under `.runtime/m6/acceptance/workspace-web-deployment-db4414eb75384a88826cfb5791b801ea/`. The built-image receipt is saved under `.runtime/m6/acceptance/workspace-web-image-84abf7b369f04359ad536bf32f5519e2/`.

After successful deployment verification, `k3d cluster stop opsproof` completed with exit code zero. Read-only Docker inspection confirmed that both cluster containers were stopped. Their recorded container exit codes were 137. The Kubernetes endpoint on port 6550 and temporary verification ports 5173 and 8090 were closed. The shutdown receipt is `shutdown-verified.json` in the deployment evidence directory.

The cluster was already running when this task began. This task performed zero cluster starts. The cluster is now stopped with its existing containers and persistent data retained.

The live API was used for read-only UI validation. Recovery mutation interactions used browser-intercepted fixtures. This update performed zero model calls, real recovery executions and AWS provisioning operations.
