"""Owned, short-lived local M6 access; administrator credentials only bootstrap it.

Fault execution uses exact-resource namespaced RBAC, never cluster-admin. The
observer has no mutation/exec rights and uses SELECT-only SQL and read-only Redis
ACL credentials. Secrets stay in process environments/private temporary configs.
"""

import json
import os
import secrets
import subprocess
import time
from urllib.parse import quote, urlsplit
from uuid import uuid4

import psycopg
from redis import Redis
from redis.exceptions import ResponseError

from scripts.m5.render_local_secrets import read_env
from scripts.m6.admission_boundary import build as build_boundaries
from scripts.m6.data_access import (
    configure_redis_observer,
    grant_sql_observer,
    revoke_sql_observer,
)
from scripts.m6.local_environment import ROOT, write_json
from scripts.m6.run_k6_local import local_prefix

NAMESPACES = (
    "opsproof-demo",
    "opsproof-control",
    "opsproof-observability",
    "argocd",
    "opsproof-gateway",
)


def observer_dsn():
    value = os.environ.get("OPSPROOF_M6_OBSERVER_DSN", "")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "postgresql"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 18033
        or not (parsed.username or "").startswith("m6_read_")
    ):
        raise ValueError("Restricted local observer SQL credentials required")
    return value


def redis_url():
    value = os.environ.get("OPSPROOF_M6_REDIS_URL", "")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "redis"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 16379
        or not (parsed.username or "").startswith("m6_")
    ):
        raise ValueError("Restricted local Redis ACL credentials required")
    return value


def control_observer_dsn():
    value = os.environ.get("OPSPROOF_M6_CONTROL_OBSERVER_DSN", "")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "postgresql"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 18032
        or not (parsed.username or "").startswith("m6_read_")
    ):
        raise ValueError("Restricted local control observer credentials required")
    return value


def read_rules():
    return [
        {
            "apiGroups": [""],
            "resources": ["pods", "services", "events"],
            "verbs": ["get", "list"],
        },
        {"apiGroups": [""], "resources": ["pods/log"], "verbs": ["get"]},
        {
            "apiGroups": ["apps"],
            "resources": ["deployments", "statefulsets", "replicasets"],
            "verbs": ["get", "list"],
        },
        {
            "apiGroups": ["argoproj.io"],
            "resources": ["applications", "rollouts", "analysisruns"],
            "verbs": ["get", "list"],
        },
        {
            "apiGroups": ["networking.k8s.io"],
            "resources": ["networkpolicies"],
            "verbs": ["get", "list"],
        },
        {
            "apiGroups": ["autoscaling"],
            "resources": ["horizontalpodautoscalers"],
            "verbs": ["get", "list"],
        },
        {
            "apiGroups": ["keda.sh"],
            "resources": ["scaledobjects"],
            "verbs": ["get", "list"],
        },
        {
            "apiGroups": ["gateway.networking.k8s.io"],
            "resources": ["httproutes"],
            "verbs": ["get", "list"],
        },
        {
            "apiGroups": ["metrics.k8s.io"],
            "resources": ["pods"],
            "verbs": ["get", "list"],
        },
    ]


def mutation_rules(scenario, capacity_mode, worker_names):
    result = {ns: [] for ns in NAMESPACES}
    if scenario == "worker_failure":
        if not worker_names or any(not name.startswith("demo-worker-") for name in worker_names):
            raise ValueError("Observed exact worker Pod names required")
        result["opsproof-demo"].append(
            {
                "apiGroups": [""],
                "resources": ["pods"],
                "resourceNames": worker_names,
                "verbs": ["delete"],
            }
        )
    if scenario == "database_connectivity":
        result["opsproof-demo"].append(
            {
                "apiGroups": ["networking.k8s.io"],
                "resources": ["networkpolicies"],
                "resourceNames": ["opsproof-namespace-traffic"],
                "verbs": ["patch"],
            }
        )
    if scenario in ("faulty_release", "downstream_latency") or capacity_mode:
        result["argocd"].append(
            {
                "apiGroups": ["argoproj.io"],
                "resources": ["applications"],
                "resourceNames": ["demo"],
                "verbs": ["patch"],
            }
        )
    if capacity_mode:
        result["opsproof-demo"] += [
            {
                "apiGroups": ["apps"],
                "resources": ["deployments"],
                "resourceNames": ["demo-worker"],
                "verbs": ["patch"],
            },
            {
                "apiGroups": ["autoscaling"],
                "resources": ["horizontalpodautoscalers"],
                "resourceNames": ["demo-api-cpu"],
                "verbs": ["delete"],
            },
            {
                "apiGroups": ["keda.sh"],
                "resources": ["scaledobjects"],
                "resourceNames": ["demo-worker-lag"],
                "verbs": ["delete"],
            },
        ]
    return result


class RestrictedAccess:
    def __init__(
        self,
        directory,
        scenario,
        capacity_mode=None,
        *,
        cleanup_only=False,
        original_state=None,
    ):
        self.directory = directory
        self.scenario = scenario
        self.capacity_mode = capacity_mode
        self.cleanup_only = cleanup_only
        self.original_state = original_state or {}
        self.identity = uuid4().hex[:16]
        self.admin = local_prefix(ROOT / ".runtime/m5/kubeconfig.yaml")
        self.owned = []
        self.private = ROOT / ".runtime/m6/private" / self.identity
        self.private.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.database_role = "m6_read_" + self.identity
        self.redis_users = []
        self.db_created = False
        self.control_db_created = False
        self.saved_environment = {}
        self.read_roles = {}
        self.closed = False
        self.intents = []

    def call(self, args, **kwargs):
        kwargs.setdefault("stderr", subprocess.PIPE)
        return subprocess.check_output(
            [*self.admin, *args], text=True, timeout=20, cwd=ROOT, **kwargs
        )

    def create(self, kind, namespace, name, **fields):
        api = (
            "v1"
            if kind == "ServiceAccount"
            else (
                "admissionregistration.k8s.io/v1"
                if kind.startswith("ValidatingAdmission")
                else "rbac.authorization.k8s.io/v1"
            )
        )
        obj = {
            "apiVersion": api,
            "kind": kind,
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": {"opsproof.io/m6-access": self.identity},
            },
            **fields,
        }
        if namespace is None:
            obj["metadata"].pop("namespace")
        intent = {"kind": kind, "namespace": namespace, "name": name}
        self.intents.append(intent)
        with (self.directory / "access-intents.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"identity": self.identity, **intent}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            created = json.loads(
                self.call(["create", "-f", "-", "-o", "json"], input=json.dumps(obj))
            )
        except subprocess.CalledProcessError as exc:
            if kind.startswith("ValidatingAdmission"):
                write_json(
                    self.directory / (name + "-compile-error.json"),
                    {"error": (exc.stderr or "")[:8000]},
                )
            raise
        self.owned.append(created)
        return created

    def __enter__(self):
        try:
            return self.setup()
        except BaseException:
            self.close()
            raise

    def setup_kubernetes(self):
        pod_lists = {
            ns: json.loads(self.call(["get", "pods", "-n", ns, "-o", "json"]))["items"]
            for ns in NAMESPACES
        }
        workers = [
            p["metadata"]["name"]
            for p in pod_lists["opsproof-demo"]
            if p["metadata"].get("labels", {}).get("opsproof.io/role") == "worker"
            and not p["metadata"].get("deletionTimestamp")
        ]
        mutations = mutation_rules(self.scenario, self.capacity_mode, workers)
        self.mutations = mutations
        if self.cleanup_only and self.scenario == "worker_failure":
            mutations["opsproof-demo"] = []
        subjects = []
        for role in ("observe", "actuate"):
            name = "m6-" + role + "-" + self.identity
            self.create(
                "ServiceAccount",
                "opsproof-control",
                name,
                automountServiceAccountToken=False,
            )
            subjects.append(
                {
                    "kind": "ServiceAccount",
                    "name": name,
                    "namespace": "opsproof-control",
                }
            )
        for ns in NAMESPACES:
            read_name = "m6-read-" + self.identity
            forward_names = [p["metadata"]["name"] for p in pod_lists[ns]]
            rules = read_rules()
            if forward_names:
                rules.append(
                    {
                        "apiGroups": [""],
                        "resources": ["pods/portforward"],
                        "resourceNames": forward_names,
                        "verbs": ["create"],
                    }
                )
            self.read_roles[ns] = self.create("Role", ns, read_name, rules=rules)
            self.create(
                "RoleBinding",
                ns,
                read_name,
                roleRef={
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "Role",
                    "name": read_name,
                },
                subjects=subjects,
            )
            if mutations[ns]:
                name = "m6-write-" + self.identity
                self.create("Role", ns, name, rules=mutations[ns])
                self.create(
                    "RoleBinding",
                    ns,
                    name,
                    roleRef={
                        "apiGroup": "rbac.authorization.k8s.io",
                        "kind": "Role",
                        "name": name,
                    },
                    subjects=[subjects[1]],
                )
        application = None
        resource = None
        if self.scenario in ("faulty_release", "downstream_latency") or self.capacity_mode:
            application = self.original_state.get("original_application") or json.loads(
                self.call(["get", "application", "demo", "-n", "argocd", "-o", "json"])
            )
        if self.scenario == "database_connectivity":
            resource = json.loads(
                self.call(
                    [
                        "get",
                        "networkpolicy",
                        "opsproof-namespace-traffic",
                        "-n",
                        "opsproof-demo",
                        "-o",
                        "json",
                    ]
                )
            )
        elif self.capacity_mode:
            resource = json.loads(
                self.call(
                    [
                        "get",
                        "deployment",
                        "demo-worker",
                        "-n",
                        "opsproof-demo",
                        "-o",
                        "json",
                    ]
                )
            )
        self.boundaries = build_boundaries(
            self.identity,
            self.scenario,
            self.capacity_mode,
            application,
            cleanup_only=self.cleanup_only,
            resource=resource,
        )
        for boundary in self.boundaries:
            self.create(
                "ValidatingAdmissionPolicy",
                None,
                boundary["name"],
                spec=boundary["spec"],
            )
            self.create(
                "ValidatingAdmissionPolicyBinding",
                None,
                boundary["name"],
                spec={
                    "policyName": boundary["name"],
                    "validationActions": ["Deny"],
                },
            )
        raw = json.loads(self.call(["config", "view", "--minify", "--raw", "-o", "json"]))
        cluster = raw["clusters"][0]["cluster"]
        self.configs = {}
        for role in ("observe", "actuate"):
            name = "m6-" + role + "-" + self.identity
            token = self.call(
                ["create", "token", name, "-n", "opsproof-control", "--duration=20m"]
            ).strip()
            config = {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [{"name": "local", "cluster": cluster}],
                "users": [{"name": role, "user": {"token": token}}],
                "contexts": [
                    {
                        "name": "k3d-opsproof",
                        "context": {"cluster": "local", "user": role},
                    }
                ],
                "current-context": "k3d-opsproof",
            }
            path = self.private / (role + ".json")
            path.write_text(json.dumps(config), encoding="utf-8")
            path.chmod(0o600)
            self.configs[role] = path
        self.verify_boundaries(application)
        return self

    def setup(self):
        self.setup_kubernetes()
        values = read_env(ROOT / ".env")
        self.demo_inspect_key = (
            values["OPSPROOF_INSPECTION_KEY"] if self.scenario == "database_connectivity" else ""
        )
        self.admin_dsn = (
            "postgresql://opsproof:"
            + quote(values["OPSPROOF_DB_PASSWORD"], safe="")
            + "@127.0.0.1:18033/opsproof"
        )
        password = secrets.token_hex(24)
        with psycopg.connect(self.admin_dsn, connect_timeout=3) as conn:
            grant_sql_observer(conn, self.database_role, password, ["jobs"])
            self.db_created = True
        self.db_dsn = (
            "postgresql://" + self.database_role + ":" + password + "@127.0.0.1:18033/opsproof"
        )
        self.control_admin_dsn = (
            "postgresql://opsproof:"
            + quote(values["OPSPROOF_CONTROL_DB_PASSWORD"], safe="")
            + "@127.0.0.1:18032/opsproof"
        )
        password = secrets.token_hex(24)
        with psycopg.connect(self.control_admin_dsn, connect_timeout=3) as conn:
            grant_sql_observer(
                conn,
                self.database_role,
                password,
                ["incidents", "incident_events", "investigations"],
            )
            self.control_db_created = True
        self.control_db_dsn = (
            "postgresql://" + self.database_role + ":" + password + "@127.0.0.1:18032/opsproof"
        )
        self.redis_urls = {}
        with Redis(host="127.0.0.1", port=16379, socket_timeout=2) as client:
            for role in ("observe", "actuate"):
                user = "m6_" + role + "_" + self.identity
                password = secrets.token_hex(24)
                self.redis_users.append(user)  # Retain ownership even if the reply is lost.
                configure_redis_observer(
                    client,
                    user,
                    password,
                    enqueue=role == "actuate" and self.scenario == "worker_failure",
                )
                self.redis_urls[role] = "redis://" + user + ":" + password + "@127.0.0.1:16379/0"
        for key, value in self.environment("actuate").items():
            self.saved_environment[key] = os.environ.get(key)
            os.environ[key] = value
        self.verify_permissions()
        write_json(
            self.directory / "restricted-access.json",
            {
                "identity": self.identity,
                "created": [
                    {
                        "kind": x["kind"],
                        "namespace": x["metadata"].get("namespace"),
                        "name": x["metadata"]["name"],
                        "uid": x["metadata"]["uid"],
                    }
                    for x in self.owned
                ],
                "observer_no_mutation_or_exec": True,
                "database_select_jobs_only": True,
                "redis_keys": ["opsproof:jobs"],
                "mutation_rules": self.mutations,
                "tokens_in_evidence": False,
            },
        )
        return self

    def verify_boundaries(self, application):
        checks = []
        for boundary in self.boundaries:
            resource = boundary["spec"]["matchConstraints"]["resourceRules"][0]["resources"][0]
            if resource == "applications":
                kind, name, ns = "application", "demo", "argocd"
                values = {
                    p["name"]: p["value"]
                    for p in application["spec"]["source"]["helm"]["parameters"]
                }
                values.update(boundary["parameters"])
                parameters = [{"name": key, "value": value} for key, value in values.items()]
                allowed = [
                    {
                        "op": "replace",
                        "path": "/spec/source/helm/parameters",
                        "value": parameters,
                    }
                ]
                if self.capacity_mode == "hpa" and not self.cleanup_only:
                    ignore = list(application["spec"].get("ignoreDifferences", []))
                    rollout = values.get("rollout.enabled") == "true"
                    ignore.append(
                        {
                            "group": "argoproj.io" if rollout else "apps",
                            "kind": "Rollout" if rollout else "Deployment",
                            "name": "demo-api",
                            "namespace": "opsproof-demo",
                            "jsonPointers": ["/spec/replicas"],
                        }
                    )
                    allowed.append(
                        {
                            "op": "add",
                            "path": "/spec/ignoreDifferences",
                            "value": ignore,
                        }
                    )
                if boundary["cleanup_only"]:
                    allowed.append(
                        {
                            "op": "add",
                            "path": "/spec/ignoreDifferences",
                            "value": application["spec"].get("ignoreDifferences", []),
                        }
                    )
                forbidden = [
                    [
                        {
                            "op": "replace",
                            "path": "/spec/source/repoURL",
                            "value": "https://example.invalid/unapproved.git",
                        }
                    ],
                    [
                        {
                            "op": "replace",
                            "path": "/spec/destination/namespace",
                            "value": "kube-system",
                        }
                    ],
                    [
                        {
                            "op": "replace",
                            "path": "/spec/source/helm/parameters",
                            "value": parameters
                            + [{"name": "api.resources.limits.memory", "value": "8Gi"}],
                        }
                    ],
                ]
            elif resource == "networkpolicies":
                kind, name, ns = (
                    "networkpolicy",
                    "opsproof-namespace-traffic",
                    "opsproof-demo",
                )
                selector = (
                    {}
                    if self.cleanup_only
                    else {
                        "matchExpressions": [
                            {
                                "key": "app.kubernetes.io/name",
                                "operator": "NotIn",
                                "values": ["opsproof-postgres"],
                            }
                        ]
                    }
                )
                allowed = [{"op": "replace", "path": "/spec/podSelector", "value": selector}]
                forbidden = [[{"op": "add", "path": "/spec/ingress", "value": [{}]}]]
            else:
                kind, name, ns = "deployment", "demo-worker", "opsproof-demo"
                allowed = [{"op": "replace", "path": "/spec/replicas", "value": 1}]
                forbidden = [
                    [
                        {
                            "op": "replace",
                            "path": "/spec/template/spec/containers/0/image",
                            "value": "unapproved.invalid/blocked:never-pulled",
                        }
                    ]
                ]

            def dry_run(changes, kind=kind, name=name, ns=ns):
                return subprocess.run(
                    [
                        "kubectl",
                        "--kubeconfig",
                        str(self.configs["actuate"]),
                        "--context",
                        "k3d-opsproof",
                        "patch",
                        kind,
                        name,
                        "-n",
                        ns,
                        "--type=json",
                        "--dry-run=server",
                        "--patch",
                        json.dumps(changes),
                        "-o",
                        "json",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )

            # Wait for admission-cache propagation by observing an actual denial.
            deadline = time.monotonic() + 20
            while True:
                denied = dry_run(forbidden[0])
                if denied.returncode and "M6 actuator change exceeds" in denied.stderr:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("M6 admission boundary did not establish an actual denial")
                time.sleep(0.5)
            accepted = dry_run(allowed)
            if accepted.returncode:
                # Store bounded policy diagnostics, never tokens or DB credentials.
                write_json(
                    self.directory / (boundary["name"] + "-diagnostic.json"),
                    {"error": accepted.stderr[:4000]},
                )
                raise RuntimeError("M6 admission policy rejected its reviewed operation")
            for changes in forbidden:
                denied = dry_run(changes)
                if not denied.returncode or "M6 actuator change exceeds" not in denied.stderr:
                    raise RuntimeError("M6 admission boundary failed a forbidden-change test")
            checks.append(
                {
                    "policy": boundary["name"],
                    "allowed_reviewed_patch": True,
                    "forbidden_changes_denied": len(forbidden),
                    "server_dry_run_only": True,
                }
            )
        write_json(self.directory / "admission-boundary-checks.json", {"checks": checks})

    def verify_kubernetes_permissions(self):
        decisions = []
        denied = [
            ("get", "secrets", "opsproof-control"),
            ("create", "pods/exec", "opsproof-demo"),
            ("create", "pods", "opsproof-control"),
            ("patch", "deployments/control-api", "opsproof-control"),
            ("delete", "pods/unrelated", "opsproof-demo"),
            ("create", "roles", "opsproof-demo"),
        ]
        for role in ("observe", "actuate"):
            checks = list(denied)
            if role == "observe":
                checks += [
                    ("patch", "applications/demo", "argocd"),
                    (
                        "patch",
                        "networkpolicies/opsproof-namespace-traffic",
                        "opsproof-demo",
                    ),
                ]
            for verb, resource, ns in checks:
                run = subprocess.run(
                    [
                        "kubectl",
                        "--kubeconfig",
                        str(self.configs[role]),
                        "--context",
                        "k3d-opsproof",
                        "auth",
                        "can-i",
                        verb,
                        resource,
                        "-n",
                        ns,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if run.stdout.strip() != "no" or run.returncode != 1:
                    raise RuntimeError(
                        "Restricted Kubernetes authorization did not deny an unsafe operation"
                    )
                decisions.append(
                    {
                        "role": role,
                        "verb": verb,
                        "resource": resource,
                        "namespace": ns,
                        "allowed": False,
                    }
                )
        return decisions

    def verify_permissions(self):
        decisions = self.verify_kubernetes_permissions()
        with psycopg.connect(self.db_dsn, connect_timeout=3) as conn:
            conn.execute("SELECT id FROM jobs LIMIT 1")
            try:
                with conn.transaction():
                    conn.execute("UPDATE jobs SET status=status WHERE false")
            except psycopg.errors.InsufficientPrivilege:
                pass
            else:
                raise RuntimeError("Observer SQL role unexpectedly permits writes")
        with Redis(host="127.0.0.1", port=16379, socket_timeout=2) as client:
            for user in self.redis_users:
                try:
                    client.acl_dryrun(user, "SET", "unrelated", "forbidden")
                except ResponseError as exc:
                    if (
                        "no permissions" not in str(exc).lower()
                        and "noperm" not in str(exc).lower()
                    ):
                        raise
                else:
                    raise RuntimeError("Redis ACL unexpectedly permits unrelated writes")
        write_json(
            self.directory / "restricted-permission-checks.json",
            {
                "kubernetes_decisions": decisions,
                "sql_write_denied": True,
                "redis_unrelated_write_denied": True,
            },
        )

    def refresh_forward_permissions(self):
        """Bind new post-rollout Pod names for observer forwards, without new verbs."""
        for ns, original in self.read_roles.items():
            pods = json.loads(self.call(["get", "pods", "-n", ns, "-o", "json"]))["items"]
            names = sorted(p["metadata"]["name"] for p in pods)
            rules = read_rules()
            if names:
                rules.append(
                    {
                        "apiGroups": [""],
                        "resources": ["pods/portforward"],
                        "resourceNames": names,
                        "verbs": ["create"],
                    }
                )
            name = original["metadata"]["name"]
            current = json.loads(self.call(["get", "role", name, "-n", ns, "-o", "json"]))
            if current["metadata"]["uid"] != original["metadata"]["uid"]:
                raise RuntimeError("Owned observation Role identity changed")
            patch = [
                {
                    "op": "test",
                    "path": "/metadata/uid",
                    "value": original["metadata"]["uid"],
                },
                {
                    "op": "test",
                    "path": "/metadata/resourceVersion",
                    "value": current["metadata"]["resourceVersion"],
                },
                {"op": "replace", "path": "/rules", "value": rules},
            ]
            self.call(
                [
                    "patch",
                    "role",
                    name,
                    "-n",
                    ns,
                    "--type=json",
                    "--patch",
                    json.dumps(patch),
                ]
            )

    def environment(self, role):
        result = {
            "OPSPROOF_M6_KUBECONFIG": str(self.configs[role]),
            "OPSPROOF_M6_OBSERVER_DSN": self.db_dsn,
            "OPSPROOF_M6_CONTROL_OBSERVER_DSN": self.control_db_dsn,
            "OPSPROOF_M6_REDIS_URL": self.redis_urls[role],
        }
        if self.demo_inspect_key:
            result["OPSPROOF_M6_DEMO_INSPECT_KEY"] = self.demo_inspect_key
        return result

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for key, old in self.saved_environment.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        if self.redis_users:
            try:
                with Redis(host="127.0.0.1", port=16379, socket_timeout=2) as client:
                    client.acl_deluser(*self.redis_users)
            except Exception as exc:
                errors.append("redis:" + type(exc).__name__)
        if self.db_created:
            try:
                with psycopg.connect(self.admin_dsn, connect_timeout=3) as conn:
                    revoke_sql_observer(conn, self.database_role, ["jobs"])
            except Exception as exc:
                errors.append("sql:" + type(exc).__name__)
        if self.control_db_created:
            try:
                with psycopg.connect(self.control_admin_dsn, connect_timeout=3) as conn:
                    revoke_sql_observer(
                        conn,
                        self.database_role,
                        ["incidents", "incident_events", "investigations"],
                    )
            except Exception as exc:
                errors.append("control_sql:" + type(exc).__name__)
        known = {
            (x["kind"], x["metadata"].get("namespace"), x["metadata"]["name"]): x
            for x in self.owned
        }
        deadline = time.monotonic() + 120
        for intent in reversed(self.intents):
            try:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Credential cleanup deadline exceeded")
                kind, namespace, name = (
                    intent["kind"],
                    intent["namespace"],
                    intent["name"],
                )
                args = [
                    "get",
                    kind,
                    name,
                    *(["-n", namespace] if namespace else []),
                    "-o",
                    "json",
                    "--ignore-not-found=true",
                ]
                raw = self.call(args).strip()
                if not raw:
                    continue
                obj = json.loads(raw)
                prior = known.get((kind, namespace, name))
                if obj["metadata"].get("labels", {}).get(
                    "opsproof.io/m6-access"
                ) != self.identity or (
                    prior and obj["metadata"]["uid"] != prior["metadata"]["uid"]
                ):
                    raise RuntimeError("Credential resource ownership changed; deletion refused")
                prefix = (
                    "/api/v1"
                    if kind == "ServiceAccount"
                    else (
                        "/apis/admissionregistration.k8s.io/v1"
                        if kind.startswith("ValidatingAdmission")
                        else "/apis/rbac.authorization.k8s.io/v1"
                    )
                )
                plural = {
                    "ServiceAccount": "serviceaccounts",
                    "Role": "roles",
                    "RoleBinding": "rolebindings",
                    "ValidatingAdmissionPolicy": "validatingadmissionpolicies",
                    "ValidatingAdmissionPolicyBinding": "validatingadmissionpolicybindings",
                }[kind]
                meta = obj["metadata"]
                body = {
                    "apiVersion": "v1",
                    "kind": "DeleteOptions",
                    "preconditions": {"uid": meta["uid"]},
                }
                self.call(
                    [
                        "delete",
                        "--raw",
                        (
                            f"{prefix}/namespaces/{meta['namespace']}/{plural}/{meta['name']}"
                            if meta.get("namespace")
                            else f"{prefix}/{plural}/{meta['name']}"
                        ),
                        "-f",
                        "-",
                    ],
                    input=json.dumps(body),
                )
                if self.call(args).strip():
                    raise RuntimeError("Credential resource still present after deletion")
            except Exception as exc:
                errors.append("rbac:" + type(exc).__name__)
        for path in self.private.glob("*.json"):
            path.unlink()
        write_json(
            self.directory / "restricted-access-cleanup.json",
            {"verified": not errors, "errors": errors, "credentials_removed": True},
        )
        if errors:
            raise RuntimeError("Restricted access cleanup incomplete; inspect retained identities")

    def __exit__(self, *_args):
        self.close()
