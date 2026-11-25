"""Render cloud namespace boundaries using reviewed private subnet and API IPs.

No DNS resolution, credentials, AWS or Kubernetes writes. Refresh API endpoint
addresses from the actual cluster before apply and whenever its addresses change.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path

NAMESPACES = (
    "opsproof-demo",
    "opsproof-control",
    "opsproof-ui",
    "opsproof-edge",
    "opsproof-observability",
)


def peer(namespace: str, labels: dict | None = None) -> dict:
    result = {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": namespace}}}
    if labels:
        result["podSelector"] = {"matchLabels": labels}
    return result


def ports(*numbers: int) -> list[dict]:
    return [{"port": number, "protocol": "TCP"} for number in numbers]


def policy(namespace: str, name: str, *, ingress=None, egress=None, selector=None) -> dict:
    spec = {"podSelector": selector or {}, "policyTypes": []}
    for key, rules in (("ingress", ingress), ("egress", egress)):
        if rules is not None:
            spec["policyTypes"].append(key.capitalize())
            spec[key] = rules
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": name, "namespace": namespace},
        "spec": spec,
    }


def build(private_subnets: list[str], api_addresses: list[str]) -> dict:
    networks = [ipaddress.ip_network(value, strict=True) for value in private_subnets]
    expected = {
        ipaddress.ip_network("10.72.20.0/24"),
        ipaddress.ip_network("10.72.21.0/24"),
    }
    if len(networks) != 2 or set(networks) != expected:
        raise ValueError(
            "Use the two exact private subnet CIDRs from the approved platform outputs"
        )
    addresses = [ipaddress.ip_address(value) for value in api_addresses]
    if not addresses or len(addresses) > 8 or len(set(addresses)) != len(addresses):
        raise ValueError("One to eight unique current API service/endpoint IPs required")
    if any(
        ip.version != 4
        or not ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
        for ip in addresses
    ):
        raise ValueError("Only verified private IPv4 API addresses are allowed")
    subnet_peers = [{"ipBlock": {"cidr": str(net)}} for net in networks]
    rows = []
    dns = {
        "to": [peer("kube-system", {"k8s-app": "kube-dns"})],
        "ports": [{"port": 53, "protocol": protocol} for protocol in ("UDP", "TCP")],
    }
    for namespace in NAMESPACES:
        rows.append(policy(namespace, "opsproof-default-deny", ingress=[], egress=[]))
        rows.append(policy(namespace, "opsproof-dns", egress=[dns]))
    for namespace in ("opsproof-demo", "opsproof-control", "opsproof-observability"):
        rows.append(
            policy(
                namespace,
                "opsproof-same-namespace",
                ingress=[{"from": [{"podSelector": {}}]}],
                egress=[{"to": [{"podSelector": {}}]}],
            )
        )
    for namespace in ("opsproof-demo", "opsproof-control"):
        rows.append(
            policy(
                namespace,
                "opsproof-telemetry",
                ingress=[{"from": [peer("opsproof-observability")], "ports": ports(8080)}],
                egress=[{"to": [peer("opsproof-observability")], "ports": ports(4318, 9090)}],
            )
        )
    rows.append(
        policy(
            "opsproof-observability",
            "opsproof-application-telemetry",
            ingress=[
                {
                    "from": [peer("opsproof-demo"), peer("opsproof-control")],
                    "ports": ports(4318, 9090),
                }
            ],
            egress=[
                {
                    "to": [peer("opsproof-demo"), peer("opsproof-control")],
                    "ports": ports(8080),
                }
            ],
        )
    )
    rows.append(
        policy(
            "opsproof-observability",
            "opsproof-kubelet-metrics",
            egress=[
                {"to": subnet_peers, "ports": ports(10250)},
                {
                    "to": [{"ipBlock": {"cidr": str(ip) + "/32"}} for ip in addresses],
                    "ports": ports(443),
                },
            ],
            selector={"matchLabels": {"app.kubernetes.io/name": "prometheus"}},
        )
    )
    rows.append(
        policy(
            "opsproof-control",
            "opsproof-demo-inspection",
            egress=[
                {
                    "to": [peer("opsproof-demo", {"opsproof.io/role": "api"})],
                    "ports": ports(8080),
                }
            ],
        )
    )
    rows.append(
        policy(
            "opsproof-demo",
            "opsproof-inspection-ingress",
            ingress=[
                {
                    "from": [
                        peer(
                            "opsproof-control",
                            {"app.kubernetes.io/part-of": "opsproof"},
                        )
                    ],
                    "ports": ports(8080),
                }
            ],
            selector={"matchLabels": {"opsproof.io/role": "api"}},
        )
    )
    rows.append(
        policy(
            "opsproof-control",
            "opsproof-private-web",
            ingress=[
                {
                    "from": [peer("opsproof-ui", {"app.kubernetes.io/name": "opsproof-web"})],
                    "ports": ports(8080),
                }
            ],
            selector={"matchLabels": {"opsproof.io/role": "api"}},
        )
    )
    rows.append(
        policy(
            "opsproof-ui",
            "opsproof-control-api",
            egress=[
                {
                    "to": [peer("opsproof-control", {"opsproof.io/role": "api"})],
                    "ports": ports(8080),
                }
            ],
        )
    )
    rows.append(
        policy(
            "opsproof-control",
            "opsproof-private-rds",
            egress=[{"to": subnet_peers, "ports": ports(5432)}],
        )
    )
    rows.append(
        policy(
            "opsproof-control",
            "opsproof-worker-observation",
            egress=[
                {
                    "to": [{"ipBlock": {"cidr": str(ip) + "/32"}} for ip in addresses],
                    "ports": ports(443),
                }
            ],
            selector={"matchLabels": {"opsproof.io/role": "evidence"}},
        )
    )
    rows.append(
        policy(
            "opsproof-demo",
            "opsproof-keda-redis",
            ingress=[{"from": [peer("keda")], "ports": ports(6379)}],
            selector={"matchLabels": {"app.kubernetes.io/name": "opsproof-redis"}},
        )
    )
    rows.append(
        policy(
            "opsproof-edge",
            "opsproof-internal-alb",
            ingress=[{"from": subnet_peers, "ports": ports(8080)}],
            selector={"matchLabels": {"app.kubernetes.io/name": "opsproof-edge"}},
        )
    )
    return {"apiVersion": "v1", "kind": "List", "items": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-subnet", action="append", required=True)
    parser.add_argument("--api-address", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.private_subnet, args.api_address)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("CLOUD_POLICIES_RENDERED; CNI enforcement requires live positive and negative tests")


if __name__ == "__main__":
    main()
