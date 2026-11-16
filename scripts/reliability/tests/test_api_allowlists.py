from copy import deepcopy

import pytest

from scripts.reliability.refresh_api_allowlists import replacement


def policy():
    return {
        "metadata": {
            "namespace": "opsproof-demo",
            "name": "rollouts-controller-egress",
        },
        "spec": {
            "podSelector": {"matchLabels": {"app.kubernetes.io/name": "argo-rollouts"}},
            "egress": [
                {
                    "to": [
                        {"ipBlock": {"cidr": "10.43.0.1/32"}},
                        {"ipBlock": {"cidr": "172.19.0.2/32"}},
                    ],
                    "ports": [{"port": 443}, {"port": 6443}],
                }
            ],
        },
    }


def test_stale_local_endpoint_can_be_replaced_without_other_authority_changes():
    original = policy()
    before = deepcopy(original)
    peers = replacement(original, ["10.43.0.1", "172.19.0.3"])
    assert {p["ipBlock"]["cidr"] for p in peers} == {"10.43.0.1/32", "172.19.0.3/32"}
    assert original == before


@pytest.mark.parametrize("address", ["0.0.0.0", "8.8.8.8", "127.0.0.1", "::1"])
def test_public_wildcard_or_loopback_api_peers_are_rejected(address):
    with pytest.raises(ValueError):
        replacement(policy(), ["10.43.0.1", address])


def test_unreviewed_policy_selector_is_rejected():
    current = policy()
    current["spec"]["podSelector"] = {}
    with pytest.raises(ValueError):
        replacement(current, ["10.43.0.1", "172.19.0.3"])
