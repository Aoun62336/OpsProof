# Identity, account preflight and cost review

Implementation is approved. AWS provisioning, image/site publication and model
requests are separate owner gates. No script in this guide has been run against
an AWS account during pre-cloud implementation.

## Identity

Use a dedicated short-lived operator role and named profile `opsproof-cloud`.
Prefer IAM Identity Center/SSO; do not create long-lived root access keys. The
role needs the reviewed Terraform bootstrap permissions and EKS access entry.
The EKS worker role and controller Pod Identity roles are separate identities.
GHCR publication uses GitHub's package token and has no AWS deployment role.

Owner setup and read-only checks:

```sh
aws configure sso --profile opsproof-cloud
aws sso login --profile opsproof-cloud
aws sts get-caller-identity --profile opsproof-cloud
aws configure get region --profile opsproof-cloud
```

Confirm the exact account, operator role ARN, Mumbai region, two distinct
available AZs, current public IPv4 `/32`, EC2 vCPU quota, two `m7i-flex.large`
offerings, and RDS `db.t4g.small` Multi-AZ PostgreSQL 18 minor availability.
Capture these facts privately; never substitute the native test fixtures.
For the selected Kubernetes version, query `eks describe-addon-versions` for
`eks-pod-identity-agent`, `vpc-cni`, `kube-proxy`, `coredns`,
`aws-ebs-csi-driver`, and `metrics-server`. Inspect `describe-addon-configuration`
for each selected exact build. Check AL2023/x86_64 compatibility. Version 1.35
is the locally validated schema target; regional availability remains an AWS
preflight, not a fact established by Terraform mock tests.

## Cost

The proposed envelope is at most 12 hours, a $15 operating allocation and $25
reserve within a $40 gross ceiling. These are review limits, not authorization,
a guarantee of free credit coverage or an automatic spending cap. Budget alerts
and Cost Explorer can lag; assign an owner and teardown timer before creation.

Copy `docs/cloud/cost-input.example.json` into `.runtime/cloud/private/`.
Populate all 17 categories with current Mumbai/account pricing and measured or
conservative usage. Hourly quantities must include exactly two worker nodes,
one EKS cluster, one NAT, one ALB and one Multi-AZ RDS instance. RDS Multi-AZ
pricing must already include its standby. Quote storage in hourly equivalents
or explicitly bounded flat allowances; include root disks, telemetry PVCs,
snapshots/backups, NAT data, cross-AZ transfer, public IPv4, Secrets Manager,
API Gateway, logs, S3 state versions, internet egress, taxes and teardown delays.
The current monitoring renderer requests six separate 1 GiB PVCs, including the
Collector's persistent queue. Include all six and their provisioning minimums in
the EBS estimate, as well as application PVCs and worker root volumes. Recompute
from the actual rendered manifests and saved plans; no fresh price is assumed.
Verify each service's credit applicability in the account; do not assume credits
cover everything or subtract guessed credits from gross cost.

```sh
python -m scripts.cloud.cost_envelope \
  --input .runtime/cloud/private/cost-input.json \
  --output .runtime/cloud/cost-review.json
```

Quotes expire after 24 hours. `REVIEW_ONLY` means the arithmetic fits the
proposed allocation; it never authorizes apply. Over-budget, incomplete, stale,
nonfinite, negative and understated core quantities are rejected or blocked.
Reprice immediately before the owner approves the actual saved plans.

## Reviewed boundaries

Two private workers across two AZs and Multi-AZ RDS improve resilience, but one
NAT is a deliberate single-AZ egress dependency. EBS-backed demo databases,
Redis and the bounded monitoring services are single-replica demonstrations.
The internal ALB's connection to the static edge is private HTTP; public API
Gateway access has managed HTTPS. This is not end-to-end TLS or a claim of
production high availability. The standard VPC CNI policy mode also has a Pod
startup policy-programming window; verify policy activation before security
acceptance and do not describe it as strict startup deny.

Official references: [EKS versions](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html),
[metrics server](https://docs.aws.amazon.com/eks/latest/userguide/metrics-server.html),
[VPC CNI policy modes](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy-configure.html),
[AWS pricing](https://aws.amazon.com/pricing/).
