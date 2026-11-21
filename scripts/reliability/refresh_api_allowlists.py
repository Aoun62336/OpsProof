"""Refresh only two existing local API /32 allowlists after a k3d IP change.

Preserves all selectors, ports, other rules and RBAC. Refuses GitOps ownership
or unreviewed policy shapes. No unrestricted network allow is introduced.
"""

import argparse
import ipaddress
import json
from uuid import uuid4

from scripts.platform.preflight import ROOT
from scripts.reliability.local_environment import LocalEnvironment, write_json

TARGETS = {
    ("opsproof-demo", "rollouts-controller-egress"): {
        "matchLabels": {"app.kubernetes.io/name": "argo-rollouts"}
    },
    ("opsproof-control", "restricted-worker-kubernetes"): {
        "matchLabels": {"app.kubernetes.io/instance": "control"},
        "matchExpressions": [
            {
                "key": "opsproof.io/role",
                "operator": "In",
                "values": ["action", "evidence"],
            }
        ],
    },
}


def replacement(policy, addresses):
    identity = (policy["metadata"]["namespace"], policy["metadata"]["name"])
    if identity not in TARGETS or policy["spec"]["podSelector"] != TARGETS[identity]:
        raise ValueError("Unexpected API allowlist target or Pod selector")
    if any("argocd" in key for key in policy["metadata"].get("annotations", {})):
        raise ValueError("GitOps-owned allowlist requires a source update")
    rule = policy["spec"]["egress"][0]
    if {p["port"] for p in rule["ports"]} != {443, 6443}:
        raise ValueError("Unexpected API ports; refusing to broaden access")
    for peer in rule["to"]:
        network = ipaddress.ip_network(peer["ipBlock"]["cidr"])
        if network.prefixlen != 32 or not network.is_private or set(peer["ipBlock"]) != {"cidr"}:
            raise ValueError("Expected existing private IPv4 /32 peers")
    peers = []
    for address in sorted(set(addresses)):
        ip = ipaddress.ip_address(address)
        if (
            ip.version != 4
            or not ip.is_private
            or ip.is_loopback
            or ip.is_unspecified
            or ip.is_link_local
            or ip.is_multicast
        ):
            raise ValueError("Only actual private local API addresses may be pinned")
        peers.append({"ipBlock": {"cidr": str(ip) + "/32"}})
    if len(peers) != 2:
        raise ValueError("Expected exactly the local API Service and one k3d endpoint")
    return peers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    output = ROOT / ".runtime/reliability/acceptance/environment" / ("api-pins-" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    env = LocalEnvironment(output)
    service = env.get("service", "kubernetes", "default")
    endpoints = env.get("endpoints", "kubernetes", "default")
    addresses = [
        service["spec"]["clusterIP"],
        *[a["ip"] for subset in endpoints["subsets"] for a in subset["addresses"]],
    ]
    records = []
    for namespace, name in TARGETS:
        policy = env.get("networkpolicy", name, namespace)
        peers = replacement(policy, addresses)
        before = policy["spec"]["egress"][0]["to"]
        changed = {json.dumps(p, sort_keys=True) for p in before} != {
            json.dumps(p, sort_keys=True) for p in peers
        }
        record = {
            "namespace": namespace,
            "name": name,
            "before": before,
            "after": peers,
            "change_needed": changed,
            "applied": False,
        }
        if args.apply and changed:
            updated = env.patch(
                "networkpolicy",
                name,
                policy,
                [{"op": "replace", "path": "/spec/egress/0/to", "value": peers}],
                namespace,
            )
            expected = json.loads(json.dumps(policy["spec"]))
            expected["egress"][0]["to"] = peers
            if updated["spec"] != expected:
                raise RuntimeError("Unexpected policy change outside exact API peers")
            record["applied"] = True
        records.append(record)
    write_json(output / "result.json", records)
    print(json.dumps(records, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
