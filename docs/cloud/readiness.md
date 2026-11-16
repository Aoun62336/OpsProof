# Cloud readiness execution

Owner approved implementation and local verification on 16 November 2026, based
on clean baseline `5dddbf6`. Real Terraform apply remains owner-operated. Publication
and model requests need their concrete release/evaluation approval. The supplied
archive is reference design material, not an authority to execute its commands.

## Scope

The approved deployment uses Mumbai, two private workers in separate AZs, one
NAT, private Multi-AZ control PostgreSQL, authenticated TLS Redis, Pod Identity,
an isolated read-only edge and a private operator console. Preserve the original
palette, independent trial proof and the local executor boundary.

## Execution order

1. Selectively integrate the 61-file package using responsibility-based paths.
2. Repair Terraform syntax/account checks and preserve Helm/local safety controls.
3. Make database role bootstrap/grants and cloud secret provisioning resumable.
4. Separate observation from mutation capabilities and adapt the existing UI.
5. Complete cloud network, secret, observability and GitOps composition.
6. Validate native infrastructure, SQL permissions, application and release checks.
7. Rehearse necessary integration locally, using isolated owned resources.
8. Test supported emulator contracts and record unsupported AWS behavior honestly.
9. Prepare and authorize a bounded AI evaluation before enabling any model.
10. Freeze the release and owner-run deployment, evidence and cleanup procedures.

## Current state

The first implementation checkpoint is verified; pre-cloud work is still in
progress. AWS writes, Terraform apply, publishing and model requests have not
been executed in this phase. The original local Kubernetes cluster is stopped.

Implemented and checked:

- Three responsibility-based Terraform roots, account guards, exact provider/
  addon inputs, private two-AZ topology, TLS-required RDS and mock-provider tests.
- Shared granular database grants, retryable owned role/Secret reconciliation,
  and read-only cloud observation without local mutation permissions.
- Original UI palette and operational cards preserved; cloud labels and runbook
  controls come from backend capabilities.
- Complete cloud value overlays, namespaces, network/secret generators, scoped
  GitOps composition and a shared existing telemetry renderer.
- Five exact controller archives/dependencies and matching upstream ALB policy,
  bounded controller requests, four-image release receipts, pinned Actions and
  public replay coverage/source-identity checks.
- Exact-ID cleanup auditing expanded to 22 resource categories; ambiguous API
  errors, partial captures and pending deletions cannot prove cleanup.

Executed verification at this checkpoint: 378 Python tests plus 21 subtests,
33 demo tests, 46 web tests, production web build, lint/format/source secret
checks, 25 local Helm profiles, six cloud application and five controller
profiles, all ten workflows parsed by actionlint, all three Terraform roots
validated and 11 native mock tests passed. The disposable TLS PostgreSQL run
separately passed the 27 existing SQL tests and five cloud role/TLS tests.

Private command/result receipts are under `.runtime/verification/source/` and
`.runtime/verification/cloud/`, including `terraform/result.json` and
`postgres/opsproof-m6-pg-test-905a08f331/result.json`. These are local execution
receipts, not proof of hosted CI, registry publication or AWS acceptance.

Still required before a release decision: Redis/container and necessary local
integration rehearsal, emulator-supported contract tests with honest limits,
new bounded AI comparison/independent factual review, final image/configuration
security review, exact release freeze and fresh owner account/cost preflight.
Actual hosted release signatures and EKS/RDS/network/edge/billing/teardown
acceptance follow the separately approved owner-run deployment.

Maintained procedures:
[identity and cost](identity-and-cost.md),
[Terraform](terraform-operations.md),
[runtime deployment](runtime-deployment.md),
[release/public evidence](release.md),
[acceptance and teardown](verification-and-teardown.md).

The source archive SHA256 is
`3a50195ffa6a0c5f2b09f9110fa8222d88d21977611c1a1d2e0e8e2fa75d3bd5`.
The exact path mapping and selective integration receipt are retained privately at
`.runtime/verification/cloud/input.json`. The earlier review documents stay in the
separate review workspace. They describe the previous paths; maintained cloud
procedures will be reconciled here.
