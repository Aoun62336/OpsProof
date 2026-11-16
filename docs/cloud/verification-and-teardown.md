> Status: existing cloud preparation. M7 implementation, publishing and Terraform apply require separate owner approval. These procedures are not evidence of cloud acceptance.

# OpsProof M7 | Cost-gated EKS evidence and teardown runbook

**NO AUTHORIZATION IS IMPLIED BY THIS RUNBOOK.** The default Terraform plan provisions no paid resources. Running a cloud test requires actual current credits/billing approval, explicit account/Region authorization and reviewed cost estimate, then a second approval of the Terraform plan. Keep the current `.runtime/m7/` artifacts locally and secret-free.

## Preflight

1. M5/M6 accepted, all six scenario evidence packages checked. No live M6 faults on EKS.
2. Confirm `AWS_PROFILE`, STS identity, Region and IAM operator role; verify actual EKS version support.
3. Confirm approved max spend and max duration; reserve time for unexpected deployment delays and teardown.
4. Confirm S3 state backend, encryption, versioning, lockfile, backups and access/recovery procedures.
5. Review Terraform plan and a **destroy/rollback plan before apply**. Assign a human to monitor actual resources and charges while they exist.
6. Confirm operator public IPv4 /32, no open 0.0.0.0/0 API endpoint, AWS region and deployment identity.
7. Check one-node compute can fit the exact intended small workload. Do not deploy the full heavy observability stack blindly on a small EC2 node.

## Representative cloud verification after approval

- Record source commit and the immutable GHCR image digests; confirm images are actually pullable by nodes.
- Provision only the approved VPC/EKS/node/add-ons. Confirm the exact cluster ARN and Region.
- Apply `opsproof-ebs-gp3` StorageClass and EKS-specific dependency Helm values. Verify EBS CSI Pod Identity and encryption behavior.
- Bootstrap the original existing Helm and GitOps application contracts in the correct namespace with **restricted generated runtime secrets**, not checked-in secrets.
- Do not assume default local `local-path` storage works on EKS.
- Validate auth, demo API and worker interactions, exact job reconciliation, rollback/Argo health where feasible and actual Kubernetes permissions.
- Capture representative logs and metrics **within the approved resource/time budget**; do not rerun all M6 destructive scenarios.
- Record all failures, incomplete controller checks, node pressure and resource identifiers.

## Mandatory teardown

- Review actual resource inventory before destroy, including EKS cluster, managed node group, ENIs, volumes, NLB/ALB if created, NAT, EIPs, IPv4, security groups, VPC endpoints, CloudWatch logs and S3 state bucket.
- Confirm there is no open operation or recoverable state requiring retention; save only sanitized evidence.
- Run the **reviewed, account-checked** Terraform destroy against the original backend/state only after explicit authorization. Never use a different backend or workspace accidentally.
- Query AWS inventory independently. Current read-only helper:

```bash
python -m scripts.cloud.aws_readonly_inventory \
  --profile opsproof-m7-inspect \
  --region <APPROVED_REGION> \
  --expected-account <APPROVED_ACCOUNT_ID> \
  --output .runtime/m7/post-destroy-inventory.json
```

- The helper is intentionally **not exhaustive**. Manual inventory in the AWS Console, other Regions, untagged resources, CloudWatch logs, EBS snapshots and state backend are required.
- If any chargeable resource remains, escalate for manual removal immediately. Do not wait for an assistant to perform future cleanup.
- Reconcile costs from Billing/Cost Explorer when usage and invoice data become available. Billing can lag.
- Mark real EKS status `PASSED`, `FAILED`, or `BLOCKED` with raw verification, never infer EKS readiness from local k3d.

## Stop and emergency rules

Stop on wrong account/region, expired credits, host/node pressure, unexpected costs, unknown resources, denied IAM, unverified cleanup, time limit overrun or missing immutable release image. For an emergency where Terraform fails, preserve the state, inventory actual AWS objects and use approved manual cleanup steps with the account owner. Don't delete state files to force a green teardown.

## Public replay

Only sanitize and curate real evidence after acceptance. `python -m scripts.cloud.build_public_replay` renders static HTML with no API calls, no auth and no mutations. It refuses suspicious fields but cannot substitute for a human privacy review. Publish only after final explicit approval.
