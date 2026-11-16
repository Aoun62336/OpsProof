> Status: existing cloud preparation. M7 implementation, publishing and Terraform apply require separate owner approval. These procedures are not evidence of cloud acceptance.

# OpsProof M7 | Temporary AWS Terraform operations

**Critical:** Not approved to provision. This repository includes a reviewable Terraform source plan, not a deployed system. Verify AWS provider/module compatibility and generated plans on the actual local toolchain before authorization.

## Directory contract

- `infra/terraform/versions.tf`: Terraform >=1.17, AWS provider 6.x and a partial S3 backend.
- `providers.tf`: approved Region and cost/reconciliation tags.
- `main.tf`: account-cost guard, module coordination, optional read-only GitHub role.
- `modules/networking`: two public subnets, VPC/IGW/routes, no NAT/LB.
- `modules/iam`: separate worker and EBS CSI Pod Identity roles.
- `modules/eks`: EKS, access entry for approved operator, single EC2 worker, core add-ons, EBS CSI.
- `values-eks.yaml` and `gp3-storageclass.yaml`: separate EKS storage policy. Keep existing k3d local-path behavior unchanged.

## Threat model and limitations

This is a low-cost temporary verification **not** production HA. One EC2 worker is a single point of failure. Node public IP and outbound internet connectivity are deliberately used to avoid NAT charges, but must not be treated as a secure private-node production topology. No inbound internet-facing application LB is provisioned. Access the Kubernetes API from the **explicit approved /32**; use tightly scoped port forwarding for local smoke tests. EKS, the node, logs, public IPv4 and PVCs all incur charges.

The dedicated EKS operator role has cluster-scoped `AmazonEKSClusterAdminPolicy` for bootstrap only and must be separately scoped in IAM to the approved account and operator. The optional GitHub OIDC role permits only `eks:DescribeCluster`, not Terraform apply or Kubernetes writes.

## Offline source checks (do not require AWS create permissions)

```bash
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
python -m unittest discover -s scripts/cloud/tests -v
```

`terraform init -backend=false` downloads providers and may access the internet. It does not create the managed EKS resources. Save the generated `.terraform.lock.hcl` for reviewed provider selection. Do not claim successful Terraform validation until it has been run in your environment; this build container has no Terraform binary or network access.

## S3 state backend (separate approved bootstrap)

The root declares `backend "s3" {}` and requires a **pre-existing** encrypted, access-controlled and versioned bucket. Review who can create it, exact cost, who can retrieve/modify state and how it will be destroyed or retained. The state contains sensitive infrastructure metadata. The S3 backend's native lock uses `use_lockfile=true`; locking uses the `.tflock` object. Do not use deprecated DynamoDB locking in a new deployment.

After approval and separately provisioning the backend, prepare `.runtime/m7/backend.private.hcl` from `infra/terraform/backend.s3.hcl.example` and set the actual bucket, key and Region. Never include AWS keys or tokens in the backend file. The example placeholders must never be used in `terraform init`.

## Actual cloud plan: only after explicit cost approval

Use a **dedicated temporary AWS provisioning role** with reviewed permissions. Use a named AWS profile. Verify STS account ID before any plan/apply.

```bash
export AWS_PROFILE=opsproof-m7-provision  # Only when role is approved and configured
aws sts get-caller-identity --profile "$AWS_PROFILE"
terraform -chdir=infra/terraform init \
  -backend-config=../../.runtime/m7/backend.private.hcl
terraform -chdir=infra/terraform plan \
  -var-file=../../.runtime/m7/cloud.private.tfvars \
  -out=../../.runtime/m7/approved.tfplan
terraform -chdir=infra/terraform show ../../.runtime/m7/approved.tfplan
```

The relative backend path is interpreted from `infra/terraform`, not the repository root. Before making changes, **inspect the plan manually**, verify account, VPC, AZs, node size, IAM permissions, EKS version, public endpoint CIDR, price and all potential chargeable resources.

**Only if explicitly authorized again after this review:**

```bash
terraform -chdir=infra/terraform apply ../../.runtime/m7/approved.tfplan
```

The availability of this command in the runbook does **not** authorize executing it. Never run it automatically from CI or from an unreviewed agent. If apply partially fails, switch immediately to the emergency cleanup runbook, inventory actual resources and preserve evidence.

## Teardown (mandatory on any deployed environment)

After the approved bounded cloud smoke, review a destroy plan against the correct backend/account and execute only under the approved cleanup procedure. Verify the actual AWS inventory separately, including unattached volumes and exposed IPs. Terraform exit code zero is not independent teardown proof.

Read `M7_CLOUD_VERIFICATION_AND_TEARDOWN.md` before provisioning.

**Sources:** https://developer.hashicorp.com/terraform/language/backend/s3 ; https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html
