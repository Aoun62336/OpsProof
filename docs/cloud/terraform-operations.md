# Terraform preparation and owner-run deployment

The maintained roots are `infra/terraform/state-bootstrap`, `platform`, and
`public-edge`. The old undeployed single-public-node preparation was replaced;
its source remains in Git history at `5dddbf6`. Do not use its old commands.
All roots default paid resources off and pin AWS provider 6.73.0. Locks contain
HashiCorp-signed Windows/Linux checksums. Tests use `mock_provider`, not AWS.

## Offline gates

From the repository root, run the following for each root:

```sh
terraform -chdir=infra/terraform/platform fmt -check -recursive
terraform -chdir=infra/terraform/platform init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/terraform/platform validate
terraform -chdir=infra/terraform/platform test
```

Replace `platform` with `state-bootstrap` and `public-edge` for their checks.
These commands are validation; a mock plan is not a deployable cloud plan.

## Private inputs

Use absolute paths to ignored `.runtime/cloud/private/` inputs and saved plans
when using `-chdir`, avoiding ambiguous relative path interpretation. Never put
credentials in tfvars/backend files. Providers and S3 backends both restrict the
approved account. The platform needs actual account/AZs/operator, fresh cost
approval reference, exact Kubernetes/PostgreSQL versions, all six addon build
pins, and the reviewed controller IAM policy path. The canonical policy is
`infra/k8s/cloud/aws-load-balancer-controller-policy.json`; its source/version
and SHA256 are recorded beside it and match the chart application version.
The native tests' minimal IAM policy is an offline fixture, never a deployment
input. Review the official policy's discovery and lifecycle wildcards before
approving its controller role.

Keep `bootstrap_master_secret_access=false` except the short credential
bootstrap phase. Initial node creation uses `bootstrap_cni_node_policy=true`;
remove that temporary node attachment after verifying aws-node Pod Identity.
These two narrowly scoped follow-up Terraform changes are planned security
steps in the deployment window, not changes to invent during apply.

## Final owner-operated sequence

1. Complete the pre-cloud checklist, release trust checks and fresh account/cost
   review. Review both the creation and cleanup procedures. Set a teardown timer.
2. Review a saved `state-bootstrap` plan, then the owner applies it. This creates
   only a dedicated encrypted, versioned, public-blocked, TLS-required S3 state
   bucket. Preserve its local bootstrap state privately; never delete state as
   a way to bypass an error.
3. Fill the platform and public-edge `backend.s3.hcl.example` files privately.
   They use separate state keys, encryption and native S3 `use_lockfile=true`.
   Use the actual bucket and allowed account, never the placeholders.
4. Initialize the platform backend, save a real plan, inspect its complete IAM,
   network and cost diff, and run `scripts.cloud.verify_domainless_plan` on its
   JSON export. This checker verifies the initial CREATE topology only; it
   cannot approve IAM, price or authorization. The owner then applies the
   reviewed saved plan. Capture partial state/resource IDs if apply fails.
5. Verify two Ready private nodes in different AZs, exact addons, Pod Identity
   and storage/network behavior. Bootstrap Kubernetes using the companion
   [runtime procedure](runtime-deployment.md). Revoke temporary master-secret
   and CNI-node access after their independent positive/negative checks.
6. Obtain the actual healthy internal ALB listener ARN from that procedure.
   Bind the public-edge plan to the same account, exact private subnets and
   VPC Link security group. Review and owner-apply that saved plan last.
7. Run all live [acceptance and cleanup checks](verification-and-teardown.md).
   No pre-cloud test can establish real EKS/RDS/ALB runtime acceptance.

Owner command pattern after approval (replace the uppercase absolute paths):

```sh
terraform -chdir=infra/terraform/platform init -input=false -lockfile=readonly -backend-config=ABSOLUTE_PRIVATE_BACKEND_FILE
terraform -chdir=infra/terraform/platform plan -input=false -var-file=ABSOLUTE_PRIVATE_TFVARS -out=ABSOLUTE_SAVED_PLAN
terraform -chdir=infra/terraform/platform show -no-color ABSOLUTE_SAVED_PLAN
terraform -chdir=infra/terraform/platform show -json ABSOLUTE_SAVED_PLAN > ABSOLUTE_PRIVATE_PLAN_JSON
python -m scripts.cloud.verify_domainless_plan --plan-json ABSOLUTE_PRIVATE_PLAN_JSON
# Owner only, after inspecting the exact plan:
terraform -chdir=infra/terraform/platform apply ABSOLUTE_SAVED_PLAN
```

There is no Terraform apply in CI. Do not use `-auto-approve`, broad imports,
force-unlocks or state removal to obtain a green result. Review state ownership
and actual account resources after any partial failure.
