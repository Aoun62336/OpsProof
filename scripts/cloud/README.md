# Cloud preparation

Private cloud preparation, release integrity, credential bootstrap and teardown auditing.

Run from the repository root using the locked control-plane tooling environment:

```sh
uv run --project apps/control-plane --locked python -m scripts.cloud.MODULE
```

Tests live in `tests/`. See [repository structure](../../docs/engineering/repository-structure.md) and the [operations guides](../../README.md#local-operation). Use an explicit local/cloud context; never infer cloud authorization from a passing source test.
