> Status: existing cloud preparation. M7 implementation, publishing and Terraform apply require separate owner approval. These procedures are not evidence of cloud acceptance.

# OpsProof M7 | AWS access, identity, IAM and cost preflight

**State:** Implemented documentation; NO cloud account provisioned, no EKS cost acceptance. This procedure runs only after local M5/M6 acceptance. Review with an authorized AWS account owner. All examples are for Windows 11 Git Bash, and operate on named profiles rather than the default account.

## 1. Define the actual cloud verification goal

We are **not** running a permanent production cluster. We need a small, temporary EKS verification of approved images and application postconditions. Current Terraform design creates a VPC with two public subnets, one managed EKS cluster and one single-node managed node group, no NAT gateway and no internet-facing load balancer. For this temporary cost-saving arrangement, the node can have a public IPv4 address; the Kubernetes API has private access plus public access restricted to the approved operator's /32. The approach is **not production private-node architecture**, not highly available, and creates billable resources.

Before proceeding, verify the current status and remaining work in `docs/history/m6-m7-integration-status.md`.

## 2. Confirm existing tools (no installation required unless absent)

```bash
aws --version
terraform version
gh --version
kubectl version --client
helm version
```

Original user toolchain includes AWS CLI v2, Terraform 1.17.1, Git Bash, kubectl, Helm and GitHub CLI. Do not reinstall or change versions blindly.

## 3. Establish a separate AWS CLI profile

If the selected AWS account supports IAM Identity Center, request the **appropriate permission set** for account inspection and, later, controlled ephemeral infrastructure administration. The read-only profile does not need EKS create/delete permissions.

```bash
aws configure sso --profile opsproof-m7-inspect
aws sso login --profile opsproof-m7-inspect
aws sts get-caller-identity --profile opsproof-m7-inspect
aws configure get region --profile opsproof-m7-inspect
```

Keep exact account identifiers out of public evidence and chat. Compare the returned account with the **approved** twelve-digit account before any further action. If Identity Center is unavailable, use a separately authorized short-lived role session. Do not create permanent IAM administrator keys to make setup easier. Avoid `aws configure` on the default profile when multiple AWS accounts exist.

## 4. Read-only Region and EKS eligibility checks

After selecting `AWS_REGION` from actual Region-specific prices and service support:

```bash
export AWS_PROFILE=opsproof-m7-inspect
export AWS_REGION=ap-south-1  # Example only; change after review
aws eks describe-cluster-versions --region "$AWS_REGION" --profile "$AWS_PROFILE"
aws ec2 describe-availability-zones --region "$AWS_REGION" --profile "$AWS_PROFILE" \
  --filters Name=state,Values=available
```

If the permission set denies these read-only actions, request the correct narrowly scoped access. Do not bypass restrictions by using another broad account automatically. Verify that the selected Kubernetes version is in EKS **standard support** and supported by the local client/controllers.

## 5. Verify current credit and actual price data

An AWS CLI identity does not prove credits cover usage. In the AWS Console, open Billing & Cost Management and verify credits **remaining, expiry, eligible services, and account-wide billing access**. Use official pricing for the chosen Region and actual instance type. At a minimum include:

- EKS cluster hourly control-plane fee, support tier and hours.
- Managed EC2 node compute and EBS root disk.
- Four application storage PVC volumes, EBS sizes, IOPS/throughput if relevant.
- Public IPv4 hourly fee, any network egress, VPC endpoints/NAT if introduced.
- Load balancers (zero in the current direct-port-forward concept), CloudWatch and logs.
- S3 remote Terraform backend storage, request operations and any retention charges.
- Contingency, verification delay, billing lag and manual emergency teardown.

Do not interpret AWS Budgets alarms as hard caps. Do not assume historical $35 credits are still present.

## 6. Offline price-envelope gate

Create `.runtime/m7/cost-estimate.private.json` by copying `docs/cloud/cost-estimate.example.json` and replace **every zero/placeholder price with actual quotes**. The example data is deliberately not usable as a cost claim.

```bash
mkdir -p .runtime/m7
cp docs/cloud/cost-estimate.example.json .runtime/m7/cost-estimate.private.json
# Edit the private copy; real source URLs, timestamp, Region, credits and pricing.
python -m scripts.cloud.cost_gate \
  --estimate .runtime/m7/cost-estimate.private.json \
  --output .runtime/m7/cost-gate.json
```

The resulting JSON explicitly has `cloud_operation_authorized=false`, even if the arithmetic is within allocation. Review the quote source, credit coverage and human approval externally.

## 7. Final decision before enabling Terraform

Capture the approved account, Region, EKS version, operator role ARN, operator IPv4 /32, exact infrastructure plan, approved maximum duration/spend, S3 backend and cleanup plan. Obtain explicit separate user permission to incur charges.

Until that happens, keep `enable_paid_resources = false` and do not run Terraform apply or any AWS create operation.

**Sources:** https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html ; https://aws.amazon.com/eks/pricing/ ; https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html
