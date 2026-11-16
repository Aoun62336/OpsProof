from pathlib import Path

import pytest

from scripts.reliability.contracts import (
    CATALOG,
    Scenario,
    assert_bounded_workload,
    assert_isolated_k3d_api,
    assert_local_scope,
)
from scripts.reliability.reconcile_jobs import parse_receipts, percentile_nearest_rank


def test_exactly_six_frozen_scenarios():
    assert set(CATALOG) == set(Scenario)
    assert len(CATALOG) == 6
    assert all(item.postconditions and item.active_m5_gate for item in CATALOG.values())


def test_workload_bounds():
    assert_bounded_workload(count=60, duration_ms=2000)
    for count, duration in ((0, 500), (121, 500), (5, 49), (5, 2001), (True, 200)):
        with pytest.raises(ValueError):
            assert_bounded_workload(count=count, duration_ms=duration)


def test_nonlocal_kubernetes_context_or_mutation_without_approval_fails(tmp_path):
    config = tmp_path / "kubeconfig.yaml"
    config.write_text("placeholder")
    assert_local_scope(kubeconfig=config, context="k3d-opsproof", mutation=False)
    with pytest.raises(ValueError):
        assert_local_scope(kubeconfig=config, context="eks-production", mutation=False)
    with pytest.raises(ValueError):
        assert_local_scope(kubeconfig=config, context="k3d-opsproof", mutation=True)
    with pytest.raises(ValueError):
        assert_local_scope(
            kubeconfig=Path("/nonexistent/kubeconfig"),
            context="k3d-opsproof",
            mutation=False,
        )


def test_receipts_are_not_success_without_exact_count(tmp_path):
    path = tmp_path / "k6.log"
    path.write_text(
        'INFO: {"kind":"m6_job_receipt","run_id":"trial-12345678",'
        '"key":"abc","id":"00000000-0000-0000-0000-000000000001",'
        '"accepted":true,"status":202}\n'
    )
    assert len(parse_receipts(path, "trial-12345678", 1)) == 1
    with pytest.raises(ValueError):
        parse_receipts(path, "trial-12345678", 2)
    with pytest.raises(ValueError):
        parse_receipts(path, "trial-wrong", 1)


def test_nearest_rank_percentile_is_bounded():
    assert percentile_nearest_rank([1.0, 3.0, 2.0], 95) == 3.0
    with pytest.raises(ValueError):
        percentile_nearest_rank([], 95)


def test_nonlocal_cluster_server_is_blocked_even_if_context_name_matches():
    assert_isolated_k3d_api("https://127.0.0.1:6550")
    for server in (
        "https://eks.us-east-1.amazonaws.com",
        "https://127.0.0.1:6443",
        "https://user:pass@127.0.0.1:6550",
        "http://127.0.0.1:6550",
    ):
        with pytest.raises(ValueError):
            assert_isolated_k3d_api(server)
