from opsproof_control.trial_catalog import TARGETS, Scenario, fixed_target


def test_catalog_is_exactly_six_fixed_targets():
    assert len(Scenario) == len(TARGETS) == 6
    assert all(fixed_target(s) == TARGETS[s] for s in Scenario)
    assert all(
        target.startswith(("opsproof-demo/", "opsproof-control/")) for target in TARGETS.values()
    )


def test_trial_worker_carries_no_kubernetes_client():
    import inspect

    from opsproof_control import trial_worker

    source = inspect.getsource(trial_worker)
    assert "kubectl" not in source
    assert "kubernetes_client" not in source


def test_packaged_catalog_matches_operator_script_catalog():
    from scripts.reliability.contracts import CATALOG

    for script_scenario, contract in CATALOG.items():
        assert fixed_target(Scenario(script_scenario.value)) == contract.target
