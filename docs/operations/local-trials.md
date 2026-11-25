# Controlled local reliability trials

This is the current local execution contract, not a statement that a cluster is
running. Accepted six-scenario and nine-capacity-trial outcomes are historical;
see [the trial results and measured profiles](../engineering/verification.md#local-results-and-screenshots).

## Preconditions

Inspect the existing local cluster, workload/image identities, absence of another
active trial and the original configuration. Use an isolated loopback kubeconfig.
Startup requires 5 GiB available host RAM and 15 GiB free workspace disk plus the
existing Docker/node checks. Active trials require 2 GiB free host RAM; stop below
1 GiB. Do not lower these gates. Never infer available capacity from reservations.

Declare the execution profile before comparing runs. The optional UI pause profile
temporarily pauses only Grafana and Argo CD UI servers, then restores and checks
them. Do not mix that profile with full-profile results. Other controllers,
collectors, data services and the operator UI remain required.

## Fault scope and outcomes

The six scenarios are worker saturation, faulty release, demo database connectivity,
worker failure, downstream latency and misleading evidence. See
[the exact catalog](scenario-catalog.md). Only supported owned local targets and
explicitly bounded mechanisms are permitted. No cloud or production target is in
scope. The Pod-deletion worker test may fail its crash hypothesis because a short
job finishes during shutdown. The recorded hard-crash pass used a separately
approved exact-container signal; it does not authorize routine host-level killing.

Persist dispatch intent before injection. Independent verification must establish
both the hypothesis and cleanup for the same dispatch/target. Unknown effects stay
indeterminate. Cleanup reconciliation appends evidence rather than rewriting a
failed trial as passed. Keep every attempt, exact job IDs, raw measurements and
manual intervention details. A ledger execution deadline does not cancel cleanup.

## Capacity and model boundaries

Capacity comparisons require at least three independently accepted equivalent
trials per fixed/API-HPA/worker-KEDA mode. Preserve actual served rates, workload
limits, scaling ownership and cleanup. k6 has its separate exact-job protocol;
do not combine incompatible measurements. Commands are in
[reliability verification](reliability-verification.md).

The NVIDIA adapter passed its recorded 42-case development qualification, while
earlier provider failures remain retained. This neither grants model-call consent
nor activates runtime AI. See [the current decision](../engineering/advisory-evaluation.md).
Stop the cluster when the approved live session finishes; preserve PVCs and proof.
