# Private Kubernetes runtime procedure

This procedure is prepared for the final owner-run AWS window. It is not evidence
that EKS was deployed. Start only after the platform saved plan is approved and
applied, all release digests/attestations verified, and the resource budget fits.
Commands below prepare local files unless they explicitly invoke AWS/Kubernetes.
Run writes yourself against the reviewed account and dedicated kubeconfig.

## Cluster and controllers

Create `.runtime/cloud/private/` with owner-only filesystem access. AWS
`eks update-kubeconfig` must use the approved profile, Mumbai, `opsproof-cloud`,
an absolute dedicated kubeconfig path and alias `opsproof-cloud-temporary`.
Never change or reuse the original local-cluster kubeconfig.

Apply `infra/k8s/cloud/namespaces.yaml`, `controller-namespaces.yaml`,
`gp3-storageclass.yaml` and `observation-rbac.yaml` only to that EKS context.
The observer Role permits only GET on `opsproof-demo/demo-worker`; no action
process receives a Kubernetes token. Application namespaces enforce restricted
Pod Security; telemetry/controller namespaces enforce baseline with restricted
audit/warnings. Keep private port-forward bindings on `127.0.0.1`.

```sh
python -m scripts.cloud.install_controllers verify
python -m scripts.cloud.render_controller_permissions --output .runtime/cloud/controller-permissions.json
# Owner applies this namespaced permission manifest before installing Argo CD.
python -m scripts.cloud.install_controllers install --execute --profile opsproof-cloud --expected-account ACTUAL_ACCOUNT_ID --kubeconfig ABSOLUTE_PRIVATE_KUBECONFIG
```

Five exact chart archives and packaged dependencies are hash locked. Installation
uses a private Helm cache and compares STS account, EKS ARN, endpoint and CA with
the dedicated kubeconfig. All controller resource limits come from
`infra/k8s/cloud/controllers/`. Verify the actual ServiceAccounts match Terraform
Pod Identity associations. Argo CD has only four application namespace Roles,
no workload Secret reads or RBAC writes, and no cluster-resource reconciliation.
External Secrets watches only `opsproof-control`, uses scoped RBAC, and has no
cluster-wide application Secret access or push-secret capability. Its certificate
controller has only a named webhook Secret permission in its own namespace;
cluster-scoped permissions cover CRD/webhook discovery and specific updates.
The ALB installer passes the verified EKS VPC ID explicitly, avoiding node
metadata discovery as a startup dependency.
The cluster registration Secret contains namespace metadata and in-cluster
ServiceAccount authentication, not an exported bearer token.

## Secrets and bootstrap

Generate credentials at the actual short deployment window, not days in advance.
Redis certificates last two days and are independently generated per namespace.
Preserve the original private files across retries; generators refuse overwrite.
Do not put model keys or existing local environment secrets into the cloud.

```sh
python -m scripts.cloud.generate_runtime_secrets --output .runtime/cloud/private/runtime-secrets.json
python -m scripts.cloud.generate_redis_security --output .runtime/cloud/private/redis-secrets.json
```

Owner applies those two private manifests. They preserve the full operator,
alert/telemetry and target-inspection contracts. Control runtime has no embedded
RDS, migration or master credentials; required separate connection Secrets are
loaded last. An absent connection Secret prevents Pod creation.

Download the current RDS trust bundle from
`https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem`, validate its
certificate contents and record SHA256 privately. Owner creates
`opsproof-rds-ca` ConfigMap in `opsproof-control` from this bundle. TLS uses
`verify-full`, hostname verification and this CA, never `sslmode=require` alone.

The two database credentials are generated outside Terraform state by
`scripts.cloud.provision_db_credentials --profile opsproof-cloud --account-id
ACTUAL_ACCOUNT_ID --execute`. This is an AWS write and must be owner-approved.
Use an explicitly pinned reviewed boto3 tooling environment; it is not an app
dependency. The helper resumes only tagged owned Secrets with the exact role
payload and preserves existing passwords; it rejects unrelated/pending Secrets.
Record the exact returned ARNs privately using account-checked read-only lookup.

Owner reviews/applies the narrow platform change enabling
`bootstrap_master_secret_access=true`. Apply `infra/k8s/cloud/secret-store.yaml`.
Generate and apply the four scoped ExternalSecrets:

```sh
python -m scripts.cloud.build_external_secret --master-secret-arn ACTUAL_RDS_MANAGED_SECRET_ARN --app-secret-arn ACTUAL_APP_SECRET_ARN --migration-secret-arn ACTUAL_MIGRATION_SECRET_ARN --rds-host ACTUAL_MUMBAI_RDS_HOST --output .runtime/cloud/rds-external-secrets.json
python -m scripts.cloud.build_db_role_jobs --image ACTUAL_CONTROL_IMAGE_BY_DIGEST --mode bootstrap --output .runtime/cloud/db-bootstrap-job.json
```

Wait for each ExternalSecret Ready, run the owner-applied bootstrap Job and
require its successful completion. The operation is transactional and retryable
only for owned restricted roles. Keep master data confined to this Job/Secret.
Do not run ordinary applications with the master user.

## Telemetry, dependencies and applications

```sh
python -m scripts.cloud.render_observability --output .runtime/cloud/telemetry.json
python -m scripts.cloud.render_gitops --release .runtime/cloud/release-manifest.json --repo-url https://github.com/Aoun62336/OpsProof.git --alb-security-group ACTUAL_PLATFORM_ALB_SG --output .runtime/cloud/applications.json
```

Review/apply the telemetry manifest; all six services use their existing shared
configuration, immutable images and bounded encrypted gp3 PVCs. Cloud Prometheus
uses headless DNS discovery to scrape every API replica and omits the local-only
canary target. No UI gets a public Service. The renderer is shared with local deployment to prevent separate
monitoring implementations. Verify its requests plus application/controller and
six-addon requests against both nodes' actual allocatable CPU, memory and Pod
limits. Reserve rolling-update and migration headroom; limits are not usage.

Before admitting application traffic, render/review the namespace policies from
the actual two `private_subnet_cidrs` outputs plus current private API backend
and Kubernetes Service IPs. Obtain backend IPs from the real cluster's
`kubernetes` EndpointSlices; workstation DNS may return public endpoint IPs.

```sh
python -m scripts.cloud.render_network_policies --private-subnet 10.72.20.0/24 --private-subnet 10.72.21.0/24 --api-address ACTUAL_PRIVATE_API_IP --api-address ACTUAL_KUBERNETES_SERVICE_IP --output .runtime/cloud/network-policies.json
```

Owner applies policies, verifies CNI activation and all intended connections,
then performs unauthorized-namespace denial probes. Control alone has private
subnet TCP/5432 egress; only its observer has API TCP/443 egress. Redis accepts
only authenticated TLS and KEDA uses its matching password/CA. The edge has no
application egress. Refresh exact API addresses after endpoint changes.

Apply the reviewed Applications and sync manually in this order: `demo-deps`
and `control-deps`, then `demo` and `control`, then `web` and `opsproof-edge`.
Do not rely on waves alone to sequence independently synchronized Applications.
Control PreSync migration uses `opsproof_migrate`, repairs explicit granular app
grants and never grants independent proof authority. Require migration success,
app readiness and the post-migration verifier Job:

```sh
python -m scripts.cloud.build_db_role_jobs --image ACTUAL_CONTROL_IMAGE_BY_DIGEST --mode verify --output .runtime/cloud/db-verifier-job.json
```

After successful independent verification, delete the bootstrap Job and master
ExternalSecret/target Secret, set `bootstrap_master_secret_access=false`, and
owner-apply that reviewed policy change. After aws-node Pod Identity works,
set `bootstrap_cni_node_policy=false` and owner-apply the attachment removal.
Verify actual denied master/node access, not merely the Terraform outputs.

Re-render Applications with `--enable-reconciliation` only after all bootstrap
checks pass; keep pruning off. Thereafter Argo is the workload reconciler. Do not
mix ongoing Helm CLI upgrades with Argo ownership. Controllers remain owned by
the installer; namespace/RBAC/secret/telemetry bootstrap remains owner-managed.

## Private UI and edge

Owner port-forwards `service/opsproof-web` in `opsproof-ui` to
`127.0.0.1:8081:8080`. The cloud values allow exactly localhost/127.0.0.1 port
8081 browser origins. Verify authenticated login, CSRF, logout, five viewport
widths, data freshness and the Temporary EKS label. Recovery/AI remain disabled.
Forward Grafana and Argo CD separately on loopback; never expose these via ALB.

The static edge Ingress creates only an internal ALB. Verify its actual healthy
target groups/listener and capture its ARN. Only then review and owner-apply
`public-edge` Terraform. Verify managed HTTPS, allowed GET routes and rejected
operator routes, collect sanitized proof, then follow the mandatory cleanup order.
