# Local acceptance evidence

These records describe the tested source revisions and local environments.
The [verification guide](../engineering/verification.md) records subsequent checks.
[Cloud readiness](../cloud/readiness.md) tracks AWS acceptance separately.

| Area | Evidence |
| --- | --- |
| Incident investigation and restricted recovery | [Local recovery acceptance](local-recovery-acceptance.md) |
| Worker shutdown and restart | [Validation](worker-shutdown-validation.md) and [portable evidence](worker-shutdown-evidence.json) |
| Kubernetes, GitOps, scaling and rollout | [Local platform acceptance](local-platform-acceptance.md) |
| Fault scenarios, exact-job verification and capacity | [Reliability trial results](reliability-trials-acceptance.md) and [acceptance matrix](reliability-acceptance-matrix.md) |
| Deployed workspace and offline evidence | [Workspace verification](workspace-ui-and-offline-evidence.md) |

The [curated public evidence dataset](../public/README.md) contains one sanitized
record for each scenario. Original reviews, interim checkpoints and raw receipts
are covered by the [retention guide](../engineering/repository-structure.md#generated-files-and-retention).
