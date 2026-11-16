# Temporary cloud infrastructure

Use the three separate state boundaries below. Run commands from the repository
root. There is no deployment entry point at this directory itself.

| Root module | Responsibility |
|---|---|
| `state-bootstrap/` | Encrypted, versioned and nonpublic Terraform state bucket |
| `platform/` | Two private AZ-scoped workers, EKS identity/add-ons, NAT and managed control database |
| `public-edge/` | Restricted API Gateway routes and VPC Link to the actual private ALB |

Each root defaults paid resources off, checks the intended account and requires
explicit owner approval. AWS provider 6.73.0 is locked. Platform files separate
networking, cluster, identity, database and edge security responsibilities. The
state boundaries reflect deployment dependencies rather than milestone numbers.

The earlier single-public-node preparation was never deployed and is retired.
Its full history remains in baseline `5dddbf6`. Existing local Kubernetes, Helm,
ledger and runtime evidence paths remain intact. No live Terraform state was
migrated or changed during this source integration.

See [cloud readiness](../../../docs/cloud/readiness.md) and
[Terraform operations](../../../docs/cloud/terraform-operations.md).
