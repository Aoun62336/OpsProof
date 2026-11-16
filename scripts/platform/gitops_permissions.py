"""Namespaced workload reconciliation permissions; no secrets or RBAC writes."""


def permissions(namespaces, *, cloud=False):
    rules = [
        {
            "apiGroups": ["argoproj.io"],
            "resources": ["rollouts", "analysistemplates"],
            "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"],
        },
        {
            "apiGroups": ["argoproj.io"],
            "resources": ["analysisruns"],
            "verbs": ["get", "list", "watch"],
        },
        {
            "apiGroups": [""],
            "resources": ["pods", "pods/log", "events"],
            "verbs": ["get", "list", "watch"],
        },
        {
            "apiGroups": [""],
            "resources": ["services", "serviceaccounts"],
            "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"],
        },
        {
            "apiGroups": [""],
            "resources": ["persistentvolumeclaims"],
            "verbs": ["get", "list", "watch", "create", "patch", "update"],
        },
        {
            "apiGroups": ["apps"],
            "resources": ["deployments", "statefulsets", "replicasets"],
            "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"],
        },
        {
            "apiGroups": ["batch"],
            "resources": ["jobs"],
            "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"],
        },
        {
            "apiGroups": ["autoscaling"],
            "resources": ["horizontalpodautoscalers"],
            "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"],
        },
        {
            "apiGroups": ["keda.sh"],
            "resources": ["scaledobjects"] + (["triggerauthentications"] if cloud else []),
            "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"],
        },
        {
            "apiGroups": ["gateway.networking.k8s.io"],
            "resources": ["httproutes"],
            "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"],
        },
    ]
    if cloud:
        rules.append(
            {
                "apiGroups": ["networking.k8s.io"],
                "resources": ["ingresses", "networkpolicies"],
                "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"],
            }
        )
    objects = []
    for ns in namespaces:
        objects.append(
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "Role",
                "metadata": {"name": "opsproof-gitops", "namespace": ns},
                "rules": rules,
            }
        )
        objects.append(
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {"name": "opsproof-gitops", "namespace": ns},
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "Role",
                    "name": "opsproof-gitops",
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": "argocd-application-controller",
                        "namespace": "argocd",
                    }
                ],
            }
        )
    return objects
