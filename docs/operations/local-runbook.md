# Local operating runbook

Open the application at http://127.0.0.1:8081. Run commands from the repository root in PowerShell. Read the latest acceptance report before repeating expensive trials.

## Cluster boundary and routine checks

Never use the default Kubernetes context: it may point to AWS. Every manual command must specify both local flags:

```powershell
kubectl --kubeconfig .runtime/platform/kubeconfig.yaml --context k3d-opsproof get applications -n argocd
kubectl --kubeconfig .runtime/platform/kubeconfig.yaml --context k3d-opsproof get pods -A
kubectl --kubeconfig .runtime/platform/kubeconfig.yaml --context k3d-opsproof get rollout demo-api -n opsproof-demo
```

Python cluster scripts use `local_cluster.py`, which requires the isolated config and validates the loopback API on port 6550. Start an existing stopped cluster with `k3d cluster start opsproof`; do not recreate it. For a genuinely new installation use `preflight.py` and `bootstrap.py`, then follow the foundation documents. Bootstrap requires 5 GiB free memory and 15 GiB disk; do not bypass the gate.

## Local GitOps updates

Commit reviewed changes locally, run `uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.platform.serve_local_git`, then update the five Applications' `spec.source.targetRevision` to that commit while preserving Helm parameters and ignore rules. The local Git server is read-only and publishes no GitHub/registry content. Verify the commit is reachable before refreshing Argo. All five Applications must be Synced/Healthy at the intended SHA.

Argo owns application resources. Do not independently run `helm upgrade` on them. Preserve narrowly scoped exceptions for Rollouts-managed route weights and recovery-managed worker replicas; do not ignore entire resources. Secrets are supplied out-of-band from ignored `.env` and must never enter Git.

Keep tested image tags/digests when application source is unchanged. For changed application source, rebuild/import the affected image, update its Application parameters and run the relevant regression checks. Controller upgrades require version/checksum review and focused compatibility validation.

## Targeted checks

```powershell
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.platform.smoke
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.platform.verify_recovery_security
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.platform.verify_release_incident
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.reliability.validate_source
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.platform.security_checks
```

Use existing evidence when code and deployment have not changed. `verify_rollouts.py --faulty-only` intentionally injects a bad release; run it only when a new failure trial is needed, with healthy baseline and enough free RAM. It restores the healthy image in its cleanup path; independently confirm Rollout Healthy and route stable/canary weights 100/0 afterward. Port-forward helpers bind loopback and clean up their owned processes.

Telemetry configuration is managed by `deploy_observability.py`. After changing alert rules, validate with Prometheus `promtool`, ensure the running configuration is refreshed, and verify actual incident delivery. Do not equate Pod readiness with end-to-end telemetry delivery.

## Restricted recovery

The sole Kubernetes operation restores `Deployment/opsproof-demo/demo-worker` from zero to one replica. The proposal requires explicit `APPROVE DEMO WORKER RESTORE`, expires after 120 seconds, and is bound to target identity/revision, incident and fresh telemetry. Active conflicting scaling ownership is rejected. Never broaden this into arbitrary kubectl, shell, selectors, namespaces or resources.

Action execution is separate from independent evidence verification. A successful PATCH is not sufficient: exact workload readiness/image, service response, exact jobs and alert resolution must pass. An uncertain network/action result is indeterminate and must be investigated before any new proposal; do not automatically replay it. The HTTP resume flow has its own verification procedure.

## Memory, cleanup and data protection

Close unused workloads or reclaim disposable filesystem cache if free memory is inadequate; do not lower safety thresholds. Release tests stop below 1 GiB free. Never delete application data to solve a test failure.

`verify_bootstrap_cleanup.py` temporarily stops the real cluster, creates and removes a uniquely named empty disposable cluster, restarts the real cluster and verifies PVC identities/default kubeconfig. This is a disruptive acceptance drill, not routine cleanup. The real `opsproof` cluster and PVCs must not be deleted without explicit authorization. Keep PostgreSQL, Redis and observability volumes and retained job history.

## Evidence

Results are in `.runtime/platform/acceptance/`; the final archive contains selected sanitized evidence and a SHA-256 manifest. Do not archive `.env`, kubeconfigs, Secret resources, cookies, tokens or raw node annotations. Remote publication and hosted CI require a separate user instruction.
