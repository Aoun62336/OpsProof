# Owner deployment session

This is the entry point for your later AWS session. No commands here have been
executed against your account. On 17 November you chose to leave account setup,
regional checks and provisioning for that session. Complete each stage and keep
its evidence before proceeding. There is no all-in-one apply command.

## 1. Prepare the reviewed source and tools

Start at `C:/Users/AOUN/Desktop/OpsProof` in PowerShell. Review the final
`codex/cloud-readiness` commit and checks before merging it into `main`; merging,
pushing and publication remain separate owner actions. Keep the original local
cluster stopped. Confirm Terraform, AWS CLI, kubectl, Helm, uv, Node and GitHub
CLI versions and authentication. Run the source, native Terraform, Helm and
security gates in [readiness](readiness.md) and the linked verification review.

Use `.runtime/cloud/private` with access restricted to your Windows account.
Store tfvars, saved plans, kubeconfig, state exports, inventory and screenshots
there. Never commit credentials, raw state or authenticated UI screenshots.

```powershell
Set-Location 'C:/Users/AOUN/Desktop/OpsProof'
$repo = (Get-Location).Path
$private = Join-Path $repo '.runtime/cloud/private'
New-Item -ItemType Directory -Force $private | Out-Null
$env:AWS_PROFILE = 'opsproof-cloud'
$env:AWS_DEFAULT_REGION = 'ap-south-1'
$env:AWS_EC2_METADATA_DISABLED = 'true'
$env:AWS_PAGER = ''
aws configure sso --profile opsproof-cloud
aws sso login --profile opsproof-cloud
aws sts get-caller-identity --profile opsproof-cloud
```

Use the SSO URL/region and dedicated role supplied by your account administrator.
Do not create root access keys. If the account lacks Identity Center, agree a
short-lived role authentication method before proceeding. Confirm the returned
account and role in the console; do not infer a permanent IAM role ARN by editing
an STS session ARN, especially for Identity Center's role path.

## 2. Collect actual account and regional facts (read only)

Set these values from your account, not the offline fixtures:

```powershell
$account = 'ACTUAL_12_DIGIT_ACCOUNT'
$operatorRole = 'ACTUAL_IAM_OPERATOR_ROLE_ARN'
$kubernetes = 'ACTUAL_STANDARD_SUPPORT_VERSION'
$postgres = 'ACTUAL_ORDERABLE_18_MINOR'
$identity = aws sts get-caller-identity --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $identity.Account -ne $account) { throw 'Wrong or unavailable account' }
aws ec2 describe-availability-zones --filters Name=state,Values=available --output json
aws ec2 describe-instance-types --instance-types m7i-flex.large --output json
aws ec2 describe-instance-type-offerings --location-type availability-zone --filters Name=instance-type,Values=m7i-flex.large --output json
aws service-quotas get-service-quota --service-code ec2 --quota-code L-1216C47A --output json
aws eks describe-cluster-versions --output json
aws rds describe-db-engine-versions --engine postgres --engine-version $postgres --output json
aws rds describe-orderable-db-instance-options --engine postgres --engine-version $postgres --db-instance-class db.t4g.small --vpc --output json
$addons = 'eks-pod-identity-agent','vpc-cni','kube-proxy','coredns','aws-ebs-csi-driver','metrics-server'
foreach ($addon in $addons) {
  aws eks describe-addon-versions --addon-name $addon --kubernetes-version $kubernetes --output json
  if ($LASTEXITCODE -ne 0) { throw "Addon discovery failed: $addon" }
}
# Repeat for every selected exact build:
aws eks describe-addon-configuration --addon-name ACTUAL_ADDON --addon-version ACTUAL_EXACT_BUILD --output json
```

Check command exit codes and save successful JSON outputs privately with UTC
capture times. Verify two chosen AZs offer the exact worker type and RDS option,
MultiAZCapable is true, free EC2 quota covers this deployment, and account EKS,
RDS, NAT/EIP, ALB/VPC Link and storage limits have room. Query each service's
quotas in Service Quotas rather than assuming the EC2 check covers them all.
Verify AL2023/x86_64, six addon compatibility/configuration schemas and standard
EKS support. The offline schema target was 1.35; any different version requires
rerender/schema review. The actual PostgreSQL minor must be locally compatible.

Confirm your current public IPv4 `/32` independently and use only that address
for operator access. Recheck it if your ISP/VPN changes. Confirm GHCR access and
all four final release digests. Get fresh Mumbai prices/credit terms in the
console, fill `cost-input.example.json` privately and run the cost review in
[identity and cost](identity-and-cost.md). Set a teardown timer and review the
single-NAT and single-replica limitations. Stop if any fact is unavailable.

## 3. Freeze and publish the reviewed release

Follow [release](release.md): protected main, successful hosted CI, manually
approved four-image GHCR workflow, pullable immutable digests, SBOMs and actual
attestation verification for all four. Retain one exact-run manifest at
`.runtime/cloud/release-manifest.json`. A local image hash is not a registry
release digest. Configure the protected release/Pages environment reviewers
before using them. Public evidence publication is optional and separately
approved; six curated historical cases are prepared, not published.

## 4. Prepare private Terraform inputs and inspect saved plans

Create a private `state-bootstrap.tfvars` with exactly these fields, substituting
real values and setting paid enablement only for your approved session:

```hcl
enable_paid_resources = true
expected_account_id = "ACTUAL_ACCOUNT"
bucket_name = "opsproof-ACTUAL_GLOBALLY_UNIQUE_SUFFIX"
approval_reference = "ACTUAL_REVIEWED_COST_AND_CHANGE_REFERENCE"
approval_acknowledgement = "I_APPROVE_TEMPORARY_OPSPROOF_AWS_CHARGES"
```

Copy the platform/public-edge examples and both backend examples into the
private directory. Fill all platform variables, including exact PostgreSQL minor,
all six addon builds, two AZs, operator role/IP and absolute reviewed ALB policy
path. Keep `bootstrap_master_secret_access=false`; CNI bootstrap starts true.
Keep public-edge disabled until the actual healthy internal ALB listener exists.
Review the complete [Terraform procedure](terraform-operations.md).

Bootstrap uses a private local state path:

```powershell
$bootstrapVars = Join-Path $private 'state-bootstrap.tfvars'
$bootstrapState = Join-Path $private 'state-bootstrap.tfstate'
$bootstrapPlan = Join-Path $private 'state-bootstrap.plan'
terraform -chdir=infra/terraform/state-bootstrap init -input=false -lockfile=readonly
terraform -chdir=infra/terraform/state-bootstrap plan -input=false "-var-file=$bootstrapVars" "-state=$bootstrapState" "-out=$bootstrapPlan"
terraform -chdir=infra/terraform/state-bootstrap show -no-color $bootstrapPlan
# Owner runs this ONLY after approving the exact displayed saved plan:
terraform -chdir=infra/terraform/state-bootstrap apply "-state=$bootstrapState" $bootstrapPlan
```

Then fill actual bucket/account in the two private S3 backend files, preserving
the separate state keys. Platform command pattern:

```powershell
$platformVars = Join-Path $private 'platform.tfvars'
$platformBackend = Join-Path $private 'platform-backend.s3.hcl'
$platformPlan = Join-Path $private 'platform.plan'
$platformJson = Join-Path $private 'platform-plan.json'
terraform -chdir=infra/terraform/platform init -input=false -lockfile=readonly "-backend-config=$platformBackend"
terraform -chdir=infra/terraform/platform plan -input=false "-var-file=$platformVars" "-out=$platformPlan"
terraform -chdir=infra/terraform/platform show -no-color $platformPlan
[IO.File]::WriteAllText($platformJson, (terraform -chdir=infra/terraform/platform show -json $platformPlan), [Text.UTF8Encoding]::new($false))
uv run --project apps/control-plane --locked python -m scripts.cloud.verify_domainless_plan --plan-json $platformJson
# Owner runs this ONLY after full IAM/network/cost review of the saved plan:
terraform -chdir=infra/terraform/platform apply $platformPlan
```

The .NET export writes UTF-8 without a BOM on both Windows PowerShell 5 and
PowerShell 7. Check native exit codes before saving/consuming outputs.
Never use `-auto-approve`, force-unlock or state removal to hide a failure.

## 5. Bootstrap and verify the private runtime

```powershell
$kubeconfig = Join-Path $private 'kubeconfig'
aws eks update-kubeconfig --name opsproof-cloud --region ap-south-1 --profile opsproof-cloud --kubeconfig $kubeconfig --alias opsproof-cloud-temporary
kubectl --kubeconfig $kubeconfig --context opsproof-cloud-temporary get nodes -L topology.kubernetes.io/zone
kubectl --kubeconfig $kubeconfig --context opsproof-cloud-temporary get pods -A
```

Use `--kubeconfig $kubeconfig --context opsproof-cloud-temporary` on every
kubectl write, including each reviewed manifest apply. Follow
[runtime deployment](runtime-deployment.md) in its exact order: namespaces/RBAC,
controllers/Pod Identity, fresh private credentials/CA, temporary master access,
bootstrap, default-deny policies, telemetry, ordered Argo Applications,
migration/verifier and permission revocation. Verify each stage before advancing.
Compare all rendered requests plus six actual addon workloads against each
node's allocatable CPU/memory/Pod capacity, storage topology, rolling/migration
headroom and measured usage. A cluster-wide sum alone cannot prove scheduling.

Port-forward the actual rendered UI service on loopback (confirm its name first):

```powershell
kubectl --kubeconfig $kubeconfig --context opsproof-cloud-temporary -n opsproof-ui get services
kubectl --kubeconfig $kubeconfig --context opsproof-cloud-temporary -n opsproof-ui port-forward service/opsproof-web 8081:8080 --address 127.0.0.1
```

Use a separate terminal for Grafana/Argo loopback forwards. Never expose those
UIs to the public edge. Keep recovery and runtime AI disabled. Only after the
internal ALB is healthy, fill real platform outputs and listener ARN in the
public-edge tfvars, initialize its separate backend, save/inspect its plan and
owner-apply that saved plan. Repeat account/cost confirmation first.

## 6. Capture proof, then remove resources

Follow [acceptance and teardown](verification-and-teardown.md). Capture source
SHA, four digests, UTC times, commands and actual results alongside screenshots:
private nodes/AZs; addon/Pod Identity health; Argo apps; authenticated UI cards and
read-only runbooks; metrics/logs/traces/alerts; RDS/PVC/TLS checks; bounded scaling;
public HTTPS marker/health and rejected write/operator paths. Redact secrets,
account identifiers, cookies, addresses and private endpoints before sharing.
Screenshots complement machine evidence; they do not replace denial probes.

Record exact resource identities before deletion, including controller-created
ALB/EBS resources. Destroy public-edge first, remove ALB/workload/PVC resources
while their controllers are alive, then platform, owned credentials, and the
versioned backend last. Save a reviewed destroy plan per root with its original
private var/backend/state files; owner-apply that exact plan. Do not blindly
empty buckets or strip finalizers. Require exact-ID audit, discovery/console
review and later settled billing checks. Record partial failures as incomplete.
