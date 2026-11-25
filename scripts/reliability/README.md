# Reliability verification

Bounded trials, independent evidence, load/capacity analysis and source/image checks.

Run from the repository root using the locked control-plane tooling environment:

```sh
uv run --project apps/control-plane --locked python -m scripts.reliability.MODULE
```

Tests live in `tests/`. See [repository structure](../../docs/engineering/repository-structure.md) and the [operations guides](../../README.md#local-operation). Use an explicit local/cloud context; never infer cloud authorization from a passing source test.

`validate_python_image --component demo|control --image LOCAL_REFERENCE` exercises
the installed artifact against disposable, network-isolated PostgreSQL and Redis
with TLS. It requires Docker, the pinned fixture images and 2 GiB free host RAM;
it never starts Kubernetes or uses provider keys. Results include runtime library
versions, positive/negative connection checks, actual API/worker behavior and
SIGTERM exit status. Owned containers and generated private keys are removed.
The release workflow runs this check for both Python artifacts before publication.

`qualify` runs the frozen deterministic reliability checks locally.
`evaluate_advisory` uses immutable evaluation inputs, a reviewed request limit and
pre-send reservations. Preparation and checks run offline. Live qualification
requires an authorized new epoch tied to its exact source and independent review.
Preserve failed and interrupted runs with their original receipts.

The NVIDIA adapter passed its recorded 42-case development suite on 24 November
2026. Runtime AI remains disabled. The
[advisory decision](../../docs/engineering/advisory-evaluation.md) records the
supported contract, qualification limits and evidence locations.
