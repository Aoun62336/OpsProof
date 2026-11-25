# Cloud acceptance, evidence and teardown

Live AWS acceptance requires verification against the deployed resources. Only the owner-run temporary AWS
window can prove EKS addons/Pod Identity, real RDS failover and TLS, EBS/CNI,
private ALB, VPC Link/API Gateway, actual image pulls and complete teardown.
Keep exact commands, timestamps, exit codes and source/image identities.

## Live acceptance

- Match the account, region and cluster ARN before every write. Verify exactly
  two private Ready workers in distinct AZs, six pinned addons, and all five
  controllers healthy. Show actual Pod Identity roles, not only association names.
- Verify encrypted gp3 PVCs, trusted RDS connections as app/migration roles,
  successful migration, denied app DDL and independent-proof writes, and absence
  of bootstrap master credentials after revocation.
- Verify Redis trusted TLS/auth works and wrong credentials, wrong CA, wrong
  hostname and cleartext fail. Test an unauthorized namespace cannot connect;
  test every intended namespace/DNS/metrics/telemetry path succeeds. Policy
  manifests alone do not establish enforcement. Test API egress with the actual
  private endpoint/service addresses and refresh policies after address changes.
- Verify unauthenticated/invalid-CSRF operator calls fail, login/logout works,
  all operational cards refresh from real evidence, and read-only cloud runbooks
  have no mutation controls. Check 1440, 1280, 768, 390 and 320-pixel widths.
- Reconcile exact job IDs/counts, stream lag and pending entries. Exercise bounded
  HPA/KEDA within the two-worker-node resource budget; verify healthy return to
  baseline. Keep destructive fault scenarios in the local sandbox and leave the fault
  executor disabled in EKS.
- Verify actual metrics with units/freshness, correlated logs and traces, alert
  authentication, and private Grafana/Argo UI health. Check current requests,
  limits, allocatable capacity and transient update headroom before scaling.
- Verify the public managed HTTPS URL serves the static marker/health, while
  POST and `/api/` are rejected. ALB must be internal with healthy target groups;
  no operator/API credentials may reach this edge.

Screenshots should show the project architecture/status, private node placement,
RDS encryption/Multi-AZ, healthy controller/addon views, operator pages, metrics,
logs/traces, Argo synchronization, bounded scaling and the read-only HTTPS edge.
Hide account IDs, endpoints that should remain private, cookies and every Secret.
Screenshots supplement command evidence; they do not replace it.

## Capture before deleting

Collect `scripts.cloud.aws_readonly_inventory` before creation, after apply and
after destroy. It intentionally includes some unfiltered service discovery to
find controller-created or incorrectly tagged resources. Inspect ownership;
listing an object is never authority to delete it. Include resources with
`Project=OpsProof`, the cloud environment tag, controller cluster tags, and the
actual Terraform states. AWS-managed RDS secrets need explicit capture too.

Maintain a private schema-2 identity manifest for `audit_aws_cleanup` with exact
account/region, `capture_complete` and all 22 `resources` category lists declared
in its `LOOKUPS` table. Explicit empty lists mean an inspected category had no
owned objects. Include every node ASG, ALB target group, NAT/EIP, ENI, EBS volume
and snapshot, RDS/manual backup, secret, log group, IAM role/policy and dedicated
backend bucket. Capture EBS IDs before PVC deletion and controller-created IDs
before uninstall. Mark partial capture false; the auditor cannot pass it. Also
review RDS retained automated backups and versioned S3 objects separately.

```sh
python -m scripts.cloud.aws_readonly_inventory --profile opsproof-cloud --region ap-south-1 --expected-account ACTUAL_ACCOUNT_ID --output .runtime/cloud/private/discovery.json
python -m scripts.cloud.audit_aws_cleanup --profile opsproof-cloud --expected-resource-ids .runtime/cloud/private/resource-identities.json --output .runtime/cloud/private/cleanup-audit.json
```

A precise service-specific absence code is required. Access denied, timeout,
unparsed errors and pending deletion stay unverified/present. Never accept a
message merely containing the word NotFound as cleanup evidence.

## Owner-run teardown order

1. Stop tests/submissions. Preserve sanitized evidence and private state exports;
   record resource IDs. Suspend automated Argo reconciliation before removals.
2. Review and owner-apply the public-edge destroy plan first. Wait for API Gateway
   and its VPC Link/ENIs to disappear, releasing the internal ALB dependency.
3. Delete the edge Ingress/Application while the ALB controller and its Pod
   Identity still work. Wait for the ALB, listeners, target groups and managed
   security groups to disappear. Do not force-remove finalizers to fake success.
4. Remove workload Applications/resources in dependency order; automatic prune is
   off, so deleting an Application alone is insufficient. Explicitly delete owned
   PVCs while EBS CSI/nodes remain available and verify volume deletion. Preserve
   any intentionally retained data with owner approval; do not claim full cleanup.
5. Remove bootstrap Jobs/ExternalSecrets/Secrets and telemetry workloads/PVCs.
   Revoke temporary role permissions. Keep controllers alive until their external
   resources and finalizers are gone.
6. Review the platform destroy plan against its original backend; owner applies
   it and confirms EKS, nodes, NAT/EIP, RDS, logs, roles and VPC deletion.
7. Run `scripts.cloud.delete_db_credentials` only for the two verified owned
   credential Secrets, using its explicit confirmation. Independently verify RDS
   managed-secret/backup cleanup; a seven-day pending Secret is still retained.
8. Export required final state/audit evidence privately. Only after both remote
   states are finished, inspect and deliberately remove all versions, delete
   markers and lock objects in the dedicated backend bucket. Review and owner
   apply the state-bootstrap destroy plan last. Never empty an unrelated bucket.
9. Run exact-ID audit plus independent discovery/console checks, including other
   Regions and untagged leftovers. Reconcile Billing/Cost Explorer after charges
   settle. Neither Terraform destroy nor an immediate dashboard proves a zero bill.

On partial failure, preserve state and capture actual objects immediately. Use
account-checked, exact-identity recovery/deletion steps with the owner; do not
blindly repeat broad deletion commands. Final status is PASSED, FAILED or BLOCKED
with remaining resources/checks listed explicitly, never inferred from local tests.
