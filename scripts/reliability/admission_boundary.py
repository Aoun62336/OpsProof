"""Per-trial CEL boundaries for exactly the mutations in the reviewed protocol.

Policies match only the temporary actuator identity. Administrators and existing
M4/M5 controllers keep their original authority. Server dry-runs must prove both
allowed and denied cases before any fault can be sent.
"""

import json

from scripts.reliability.local_environment import ROOT


def unchanged(path):
    new, old = "object." + path, "oldObject." + path
    return f"(has({new}) == has({old}) && (!has({new}) || {new} == {old}))"


def cel_literal(value):
    # CEL map/list literals are homogeneous at compile time. Explicit dyn values
    # retain JSON value types while allowing structured heterogeneous objects.
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                json.dumps(key) + ":dyn(" + cel_literal(item) + ")" for key, item in value.items()
            )
            + "}"
        )
    if isinstance(value, list):
        return "[" + ",".join("dyn(" + cel_literal(item) + ")" for item in value) + "]"
    return json.dumps(value)


def pinned(path, reference):
    value = reference
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return "!has(object." + path + ")"
        value = value[part]
    return "has(object." + path + ") && object." + path + " == " + cel_literal(value)


def policy(name, username, namespace, resource, group, target, expressions):
    return {
        "kind": "ValidatingAdmissionPolicy",
        "name": name,
        "spec": {
            "failurePolicy": "Fail",
            "matchConstraints": {
                "resourceRules": [
                    {
                        "apiGroups": [group],
                        "apiVersions": ["*"],
                        "operations": ["UPDATE"],
                        "resources": [resource],
                        "scope": "Namespaced",
                    }
                ]
            },
            "matchConditions": [
                {
                    "name": "owned-actuator",
                    "expression": "request.userInfo.username == " + json.dumps(username),
                },
                {
                    "name": "exact-target",
                    "expression": "request.namespace == "
                    + json.dumps(namespace)
                    + " && object.metadata.name == "
                    + json.dumps(target),
                },
            ],
            "validations": [
                {
                    "expression": expression,
                    "reason": "Forbidden",
                    "message": "M6 actuator change exceeds the reviewed trial boundary",
                }
                for expression in expressions
            ],
        },
    }


def build(
    identity,
    scenario,
    capacity_mode,
    application=None,
    *,
    cleanup_only=False,
    resource=None,
):
    username = "system:serviceaccount:opsproof-control:m6-actuate-" + identity
    metadata = [
        unchanged("metadata." + field)
        for field in ("labels", "annotations", "finalizers", "ownerReferences")
    ]
    result = []
    if scenario == "database_connectivity":
        selector = "object.spec.podSelector"
        empty = f"(!has({selector}.matchLabels) || size({selector}.matchLabels)==0)"
        original = f"(!has({selector}.matchExpressions) || size({selector}.matchExpressions)==0)"
        exclusion = (
            f"(has({selector}.matchExpressions) && size({selector}.matchExpressions)==1 && "
            f"{selector}.matchExpressions[0].key=='app.kubernetes.io/name' && "
            f"{selector}.matchExpressions[0].operator=='NotIn' && "
            f"{selector}.matchExpressions[0].values==['opsproof-postgres'])"
        )
        expressions = metadata + [
            unchanged("spec." + field) for field in ("ingress", "egress", "policyTypes")
        ]
        expressions.append(
            f"{empty} && ({original})"
            if cleanup_only
            else f"{empty} && ({original} || {exclusion})"
        )
        if resource:
            expressions.append(pinned("metadata.uid", resource))
        result.append(
            policy(
                "m6-database-" + identity,
                username,
                "opsproof-demo",
                "networkpolicies",
                "networking.k8s.io",
                "opsproof-namespace-traffic",
                expressions,
            )
        )
    if capacity_mode:
        expressions = metadata + ["object.spec.replicas == 1"]
        expressions += [
            unchanged("spec." + field)
            for field in (
                "selector",
                "template",
                "strategy",
                "minReadySeconds",
                "revisionHistoryLimit",
                "paused",
                "progressDeadlineSeconds",
            )
        ]
        if resource:
            expressions.append(pinned("metadata.uid", resource))
        result.append(
            policy(
                "m6-worker-" + identity,
                username,
                "opsproof-demo",
                "deployments",
                "apps",
                "demo-worker",
                expressions,
            )
        )
    if scenario not in ("faulty_release", "downstream_latency") and not capacity_mode:
        return result
    if application is None:
        raise ValueError("Original demo Application required for GitOps boundary")
    spec = application["spec"]
    if (
        spec["source"]["repoURL"]
        != "http://opsproof-git.opsproof-git.svc.cluster.local:8080/repo.git"
        or spec["destination"]["namespace"] != "opsproof-demo"
    ):
        raise ValueError("GitOps boundary requires the approved local demo source")
    params = spec["source"]["helm"]["parameters"]
    old = {p["name"]: p["value"] for p in params}
    if len(old) != len(params):
        raise ValueError("Duplicate original Helm parameter identities")
    desired = {}
    if scenario == "faulty_release":
        records = json.loads((ROOT / ".runtime/m5/acceptance/release-images.json").read_text())
        desired = {"rollout.image": next(r["image"] for r in records if r["release"] == "faulty")}
    elif scenario == "downstream_latency":
        desired = {
            "demoDownstream.enabled": "true",
            "demoDownstream.delayMs": "1000",
            "telemetry.enabled": "true",
        }
    if capacity_mode:
        desired = {
            "autoscaling.hpa.enabled": str(capacity_mode == "hpa").lower(),
            "autoscaling.keda.enabled": str(capacity_mode == "keda").lower(),
            "worker.recoveryManaged": "false",
            "autoscaling.hpa.rolloutTargetEnabled": str(
                capacity_mode == "hpa" and old.get("rollout.enabled") == "true"
            ).lower(),
        }
    allowed = {
        key: sorted(set(([value] if not cleanup_only else []) + ([old[key]] if key in old else [])))
        for key, value in desired.items()
    }
    expressions = metadata + [pinned("metadata.uid", application)]
    expressions += [
        pinned("spec.destination." + field, application)
        for field in ("server", "name", "namespace")
    ]
    expressions += [
        pinned("spec." + field, application)
        for field in (
            "project",
            "destination",
            "sources",
            "syncPolicy",
            "revisionHistoryLimit",
            "info",
        )
    ]
    expressions += [
        pinned("spec.source." + field, application)
        for field in (
            "repoURL",
            "path",
            "targetRevision",
            "chart",
            "ref",
            "plugin",
            "directory",
            "kustomize",
        )
    ]
    expressions += [
        pinned("spec.source.helm." + field, application)
        for field in (
            "releaseName",
            "valueFiles",
            "values",
            "valuesObject",
            "fileParameters",
            "ignoreMissingValueFiles",
            "passCredentials",
            "skipCrds",
            "skipSchemaValidation",
            "skipTests",
            "version",
            "kubeVersion",
            "apiVersions",
            "namespace",
        )
    ]
    new_params = "object.spec.source.helm.parameters"
    old_params = "oldObject.spec.source.helm.parameters"
    keys = json.dumps(sorted(allowed))
    choices = json.dumps(allowed)
    expressions += [
        f"{new_params}.all(p, {new_params}.filter(q,q.name==p.name).size()==1)",
        f"{new_params}.all(p, p.name in {keys} ? p.value in {choices}[p.name] "
        f": {old_params}.exists(o,o==p))",
        f"{old_params}.all(o, o.name in {keys} || {new_params}.exists(p,p==o))",
    ]
    old_ignore = cel_literal(spec.get("ignoreDifferences", []))
    new_ignore = "(has(object.spec.ignoreDifferences) ? object.spec.ignoreDifferences : [])"
    extra = "false"
    if capacity_mode == "hpa" and not cleanup_only:
        kind = "Rollout" if old.get("rollout.enabled") == "true" else "Deployment"
        group = "argoproj.io" if kind == "Rollout" else "apps"
        extra = (
            "(e.group=="
            + json.dumps(group)
            + " && e.kind=="
            + json.dumps(kind)
            + " && e.name=='demo-api' && e.namespace=='opsproof-demo'"
            + " && e.jsonPointers==['/spec/replicas']"
            + " && !has(e.jqPathExpressions) && !has(e.managedFieldsManagers))"
        )
    expressions += [
        f"{new_ignore}.all(e, {old_ignore}.exists(o,o==e) || {extra})",
        f"{old_ignore}.all(o, {new_ignore}.exists(e,e==o))",
    ]
    value = policy(
        "m6-gitops-" + identity,
        username,
        "argocd",
        "applications",
        "argoproj.io",
        "demo",
        expressions,
    )
    value["parameters"] = (
        {key: old[key] for key in desired if key in old} if cleanup_only else desired
    )
    value["cleanup_only"] = cleanup_only
    result.append(value)
    return result
