"""Six fixed local mechanisms. No caller-supplied Kubernetes command or URL.

These adapters collect observations; only the separate verifier can establish
postconditions. A returned Kubernetes acknowledgment is never recovery proof.
Live acceptance requires executing these against the actual local environment.
"""

import json
import re
import time
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import UUID, uuid4

from opsproof_control.m6_diagnosis import Observation, deterministic_m6

from scripts.m6.local_environment import ROOT, fresh_database_probe, http, utc


def selected(labels, selector):
    """Kubernetes LabelSelector matching for inspection of additive policies."""
    if any(labels.get(k) != v for k, v in selector.get("matchLabels", {}).items()):
        return False
    for rule in selector.get("matchExpressions", []):
        key, op, values = rule["key"], rule["operator"], rule.get("values", [])
        if op == "In" and labels.get(key) not in values:
            return False
        if op == "NotIn" and labels.get(key) in values:
            return False
        if op == "Exists" and key not in labels:
            return False
        if op == "DoesNotExist" and key in labels:
            return False
        if op not in ("In", "NotIn", "Exists", "DoesNotExist"):
            raise ValueError("Unsupported policy selector; refusing isolation assumption")
    return True


def database_exclusion(policies, labels):
    matching = {
        p["metadata"]["name"]: p
        for p in policies
        if selected(labels, p["spec"].get("podSelector", {}))
    }
    if set(matching) != {"opsproof-default-deny", "opsproof-namespace-traffic"}:
        raise ValueError("Unreviewed additive policies select PostgreSQL; fault refused")
    policy = matching["opsproof-namespace-traffic"]
    if (
        policy["spec"].get("podSelector") != {}
        or labels.get("app.kubernetes.io/name") != "opsproof-postgres"
        or labels.get("app.kubernetes.io/instance") != "demo-deps"
    ):
        raise ValueError("PostgreSQL/policy identity differs from the reviewed profile")
    annotations = policy["metadata"].get("annotations", {})
    if any("argocd" in key for key in annotations) or policy["metadata"].get("ownerReferences"):
        raise ValueError("GitOps-owned policy requires an explicit source ownership protocol")
    return policy, {
        "matchExpressions": [
            {
                "key": "app.kubernetes.io/name",
                "operator": "NotIn",
                "values": ["opsproof-postgres"],
            }
        ]
    }


class Adapter:
    scenario = ""
    target_resource = ("deployment", "demo-worker", "opsproof-demo")

    def __init__(self, environment):
        self.env = environment
        self.state = {
            "scenario": self.scenario,
            "job_ids": [],
            "submitted_keys": [],
            "injection_started_at": None,
            "observed": False,
        }

    def snapshot(self):
        resource = self.env.get(*self.target_resource)
        metadata = resource["metadata"]
        self.state["target_uid"] = metadata["uid"]
        self.state["target_version"] = metadata["resourceVersion"]
        worker = self.env.get("deployment", "demo-worker")
        self.state["worker_image"] = worker["spec"]["template"]["spec"]["containers"][0]["image"]
        return self.state

    def checkpoint(self):
        return self.env.save("adapter-state", self.state)

    def job(self, duration=2000):
        self.env.guard()
        key = "m6-fault-" + uuid4().hex
        self.state["submitted_keys"].append(key)
        # Save intent before submitting, so a lost HTTP response retains the key.
        self.checkpoint()
        status, result = http(
            18088,
            "/api/v1/jobs",
            body={"duration_ms": duration},
            headers={"Idempotency-Key": key},
        )
        if status != 202 or not result:
            raise RuntimeError(
                "Job submission unknown/failed; retained key requires reconciliation"
            )
        job_id = str(UUID(result["id"]))
        if job_id in self.state["job_ids"]:
            raise RuntimeError("Duplicate durable job identity")
        self.state["job_ids"].append(job_id)
        self.checkpoint()
        return result

    def wait_jobs(self, seconds=180, *, guard=True):
        deadline = time.monotonic() + seconds
        jobs = []
        while time.monotonic() < deadline:
            if guard:
                self.env.guard()
            jobs = []
            for job_id in self.state["job_ids"]:
                status, row = http(18088, "/api/v1/jobs/" + str(UUID(job_id)))
                if status != 200 or row.get("id") != job_id or row.get("status") == "failed":
                    raise RuntimeError("Exact job identity/state failed verification")
                jobs.append(row)
            queue = self.env.queue()
            self.env.save("job-observation", {"jobs": jobs, "queue": queue})
            if (
                all(row["status"] == "completed" for row in jobs)
                and queue["lag"] == queue["pending"] == 0
            ):
                return jobs
            time.sleep(2)
        raise TimeoutError("Exact jobs/queue failed to drain within deadline")

    def cleanup(self):
        return {
            "jobs": self.wait_jobs(180, guard=False),
            "mechanism": "finite_load_drained",
        }


class Saturation(Adapter):
    scenario = "worker_saturation"

    def inject(self):
        self.state["injection_started_at"] = utc()
        return {
            "first_job": self.job(),
            "mechanism": "60 ordinary 2000-ms durable jobs",
        }

    def observe(self):
        for _ in range(59):
            self.job()
        peak = 0
        samples = []
        for _ in range(90):
            self.env.guard()
            queue = self.env.queue()
            worker = self.env.get("deployment", "demo-worker")
            sample = {
                "at": utc(),
                "queue": queue,
                "desired": worker["spec"]["replicas"],
                "ready": worker["status"].get("readyReplicas", 0),
            }
            samples.append(sample)
            self.env.save("queue-sample", sample)
            if queue["lag"] is None:
                raise RuntimeError("Unknown Redis lag cannot establish saturation")
            peak = max(peak, queue["lag"])
            if queue["lag"] == 0 and queue["pending"] == 0:
                break
            time.sleep(2)
        jobs = self.wait_jobs()
        self.state["observed"] = peak >= 10 and all(j["attempts"] == 1 for j in jobs)
        return {
            "hypothesis_observed": self.state["observed"],
            "peak_lag": peak,
            "samples": samples,
            "jobs": jobs,
            "recovery_attribution": "fixed worker processing",
        }


class WorkerFailure(Adapter):
    scenario = "worker_failure"

    def inject(self):
        pods = self.env.get("pods")["items"]
        pods = [
            p
            for p in pods
            if p["metadata"]["labels"].get("opsproof.io/role") == "worker"
            and not p["metadata"].get("deletionTimestamp")
        ]
        if len(pods) != 1 or pods[0]["status"]["phase"] != "Running":
            raise RuntimeError("Exactly one running demo worker required")
        pod = pods[0]
        name, uid = pod["metadata"]["name"], pod["metadata"]["uid"]
        if not re.fullmatch(r"demo-worker-[a-z0-9-]+", name):
            raise ValueError("Unexpected worker Pod name")
        self.state["old_worker"] = {"name": name, "uid": uid}
        job = self.job()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            self.env.guard()
            _, row = http(18088, "/api/v1/jobs/" + job["id"])
            if row and row["status"] == "processing":
                break
            time.sleep(0.03)
        else:
            raise RuntimeError("No in-flight job observed before interruption")
        pending = self.env.queue()
        if pending["pending"] < 1:
            raise RuntimeError("Actual Redis pending work required before process loss")
        current = self.env.get("pod", name)
        if current["metadata"]["uid"] != uid:
            raise RuntimeError("Worker identity changed before termination")
        options = {
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "gracePeriodSeconds": 0,
            "preconditions": {
                "uid": uid,
                "resourceVersion": current["metadata"]["resourceVersion"],
            },
        }
        self.state["injection_started_at"] = utc()
        self.checkpoint()
        self.env.guard()
        response = json.loads(
            self.env.command(
                [
                    "delete",
                    "--raw",
                    f"/api/v1/namespaces/opsproof-demo/pods/{name}",
                    "-f",
                    "-",
                ],
                input=json.dumps(options),
            )
        )
        return {
            "mechanism": "UID-preconditioned zero-grace single worker Pod termination",
            "pod": self.state["old_worker"],
            "pending_before": pending,
            "response_kind": response.get("kind"),
            "job_before": row,
        }

    def observe(self):
        jobs = self.wait_jobs()
        pods = self.env.get("pods")["items"]
        replacement = [
            p
            for p in pods
            if p["metadata"]["labels"].get("opsproof.io/role") == "worker"
            and p["metadata"]["uid"] != self.state["old_worker"]["uid"]
            and p["status"]["phase"] == "Running"
        ]
        if len(replacement) != 1:
            raise RuntimeError("Replacement and interrupted-attempt recovery not established")
        if jobs[0]["attempts"] != 2:
            return {
                "hypothesis_observed": False,
                "jobs": jobs,
                "replacement_uid": replacement[0]["metadata"]["uid"],
                "reason": "Worker replacement completed without exactly one interrupted retry",
            }
        job_id = str(UUID(jobs[0]["id"]))
        duplicate = self.env.duplicate_job(job_id)
        time.sleep(3)
        after = self.wait_jobs()
        self.state["observed"] = jobs == after
        self.state["replacement_uid"] = replacement[0]["metadata"]["uid"]
        return {
            "hypothesis_observed": self.state["observed"],
            "jobs": after,
            "duplicate_stream_id": duplicate,
            "replacement_uid": self.state["replacement_uid"],
            "recovery_attribution": "Kubernetes replacement, Redis reclaim, PostgreSQL fencing",
            "semantics": "at-least-once processing; no duplicate durable completion observed",
        }


class DatabaseConnectivity(Adapter):
    scenario = "database_connectivity"
    target_resource = ("statefulset", "demo-deps-postgres", "opsproof-demo")

    def snapshot(self):
        super().snapshot()
        code, probe = fresh_database_probe()
        if (
            code != 200
            or not probe
            or probe.get("ready") is not True
            or probe.get("connection") != "fresh"
        ):
            raise RuntimeError("Enabled authenticated fresh-database probe required at baseline")
        pod = self.env.get("pod", "demo-deps-postgres-0")
        policies = self.env.get("networkpolicies")["items"]
        original, exclusion = database_exclusion(policies, pod["metadata"]["labels"])
        self.state["policy"] = {
            "metadata": original["metadata"],
            "spec": original["spec"],
        }
        self.state["exclusion"] = exclusion
        return self.state

    def inject(self):
        self.state["sentinel_job"] = self.job(50)["id"]
        self.wait_jobs()
        original = self.state["policy"]
        self.state["injection_started_at"] = utc()
        self.state["policy_change_attempted"] = True
        self.checkpoint()
        changed = self.env.patch(
            "networkpolicy",
            "opsproof-namespace-traffic",
            original,
            [
                {
                    "op": "replace",
                    "path": "/spec/podSelector",
                    "value": self.state["exclusion"],
                }
            ],
        )
        self.state["changed_spec"] = changed["spec"]
        return {
            "mechanism": "exclude only demo PostgreSQL from existing additive allow policy",
            "policy_uid": changed["metadata"]["uid"],
            "resource_version": changed["metadata"]["resourceVersion"],
        }

    def observe(self):
        observations = []
        # Leave a bounded observation window for the independent process.
        # One fast executor response cannot substitute for its observations.
        until = time.monotonic() + 7
        while time.monotonic() < until:
            self.env.guard()
            try:
                demo, probe = fresh_database_probe(
                    timeout=min(3, max(0.1, until - time.monotonic()))
                )
            except OSError, TimeoutError:
                demo, probe = None, None
            control = http(18090, "/health/ready", timeout=1)[0]
            observations.append(
                {
                    "at": utc(),
                    "demo_ready_status": demo,
                    "control_ready_status": control,
                }
            )
            if control != 200:
                raise RuntimeError("Control-plane health affected; restore immediately")
            if demo == 503 and probe == {"detail": "Fresh database connection unavailable"}:
                self.state["observed"] = True
            time.sleep(0.5)
        self.env.save("database-readiness", observations)
        return {
            "hypothesis_observed": self.state["observed"],
            "readiness": observations,
            "recovery_attribution": "explicit restoration of exact original allow policy",
        }

    def cleanup(self):
        original = self.state["policy"]
        current = self.env.get("networkpolicy", "opsproof-namespace-traffic")
        if current["metadata"]["uid"] != original["metadata"]["uid"]:
            raise RuntimeError("NetworkPolicy identity changed; restore ownership is uncertain")
        if current["spec"] != original["spec"]:
            expected = dict(original["spec"], podSelector=self.state["exclusion"])
            if current["spec"] != expected:
                raise RuntimeError("Concurrent policy change; refusing to overwrite it")
            patch = [
                {
                    "op": "test",
                    "path": "/metadata/uid",
                    "value": current["metadata"]["uid"],
                },
                {
                    "op": "test",
                    "path": "/metadata/resourceVersion",
                    "value": current["metadata"]["resourceVersion"],
                },
                {"op": "replace", "path": "/spec", "value": original["spec"]},
            ]
            self.env.command(
                [
                    "patch",
                    "networkpolicy",
                    "opsproof-namespace-traffic",
                    "-n",
                    "opsproof-demo",
                    "--type=json",
                    "--patch",
                    json.dumps(patch),
                ]
            )
        until = time.monotonic() + 60
        while fresh_database_probe()[0] != 200:
            if time.monotonic() >= until:
                raise TimeoutError("Database client connectivity did not recover")
            time.sleep(1)
        self.job(50)
        return {"policy_restored": True, "jobs": self.wait_jobs(120, guard=False)}


class FaultyRelease(Adapter):
    scenario = "faulty_release"
    target_resource = ("rollout", "demo-api", "opsproof-demo")

    def snapshot(self):
        super().snapshot()
        rollout = self.env.get("rollout", "demo-api")
        if rollout.get("status", {}).get("phase") != "Healthy":
            raise RuntimeError("Healthy stable Rollout required")
        images = json.loads((ROOT / ".runtime/m5/acceptance/release-images.json").read_text())
        faulty = next(item for item in images if item["release"] == "faulty")
        stable_image = rollout["spec"]["template"]["spec"]["containers"][0]["image"]
        if faulty["image"] == stable_image or not re.fullmatch(
            r"sha256:[a-f0-9]{64}", faulty["image_id"]
        ):
            raise RuntimeError("Distinct, reviewed local bad candidate identity required")
        self.state.update(
            original_application=self.env.get("application", "demo", "argocd"),
            stable_image=stable_image,
            faulty_image=faulty,
        )
        return self.state

    def inject(self):
        self.state["injection_started_at"] = utc()
        params = {
            p["name"]: p["value"]
            for p in self.state["original_application"]["spec"]["source"]["helm"]["parameters"]
        }
        params["rollout.image"] = self.state["faulty_image"]["image"]
        self.state["expected_parameters"] = [{"name": k, "value": v} for k, v in params.items()]
        self.checkpoint()
        changed = self.env.configure_demo({"rollout.image": self.state["faulty_image"]["image"]})
        return {
            "mechanism": "Argo-owned bad candidate revision",
            "candidate": self.state["faulty_image"],
            "application_uid": changed["metadata"]["uid"],
            "source_parameters": self.state["expected_parameters"],
        }

    def observe(self):
        requests = []
        until = time.monotonic() + 240
        while time.monotonic() < until:
            self.env.guard()
            trace_id = uuid4().hex
            status, _ = http(
                18081,
                "/api/v1/stats",
                headers={"traceparent": f"00-{trace_id}-{uuid4().hex[:16]}-01"},
            )
            requests.append({"at": utc(), "status": status, "trace_id": trace_id})
            rollout = self.env.get("rollout", "demo-api")
            if rollout.get("status", {}).get("abort") and any(r["status"] == 500 for r in requests):
                break
            time.sleep(0.5)
        analyses = self.env.get("analysisruns")["items"]
        started = datetime.fromisoformat(self.state["injection_started_at"])
        failed = [
            a
            for a in analyses
            if a.get("status", {}).get("phase") in ("Failed", "Error")
            and datetime.fromisoformat(a["metadata"]["creationTimestamp"].replace("Z", "+00:00"))
            >= started
        ]
        self.state["observed"] = bool(
            rollout.get("status", {}).get("abort")
            and failed
            and any(r["status"] == 500 for r in requests)
        )
        self.state["failed_trace_ids"] = [r["trace_id"] for r in requests if r["status"] == 500]
        return {
            "hypothesis_observed": self.state["observed"],
            "requests": requests,
            "analysis_runs": [
                {"name": a["metadata"]["name"], "status": a.get("status")} for a in failed
            ],
            "recovery_attribution": "Argo Rollouts analysis rejection/abort, not OpsProof recovery",
        }

    def cleanup(self):
        current = self.env.get("application", "demo", "argocd")
        original = self.state["original_application"]
        if (
            current["spec"]["source"]["helm"]["parameters"]
            != original["spec"]["source"]["helm"]["parameters"]
        ):
            self.env.restore_demo(original, self.state["expected_parameters"])
        until = time.monotonic() + 180
        while time.monotonic() < until:
            rollout = self.env.get("rollout", "demo-api")
            route = self.env.get("httproute", "demo-release")
            refs = route["spec"]["rules"][0]["backendRefs"]
            weights = {r["name"]: r.get("weight", 1) for r in refs}
            if (
                rollout.get("status", {}).get("phase") == "Healthy"
                and weights.get("demo-api") == 100
                and weights.get("demo-api-canary") == 0
                and all(http(18081, "/api/v1/stats")[0] == 200 for _ in range(5))
            ):
                return {"stable_serving": True, "route_weights": weights}
            time.sleep(2)
        raise TimeoutError("Stable Rollout and service restoration not established")


class DownstreamLatency(FaultyRelease):
    scenario = "downstream_latency"
    target_resource = ("deployment", "demo-worker", "opsproof-demo")

    def snapshot(self):
        Adapter.snapshot(self)
        app = self.env.get("application", "demo", "argocd")
        params = {p["name"]: p["value"] for p in app["spec"]["source"]["helm"]["parameters"]}
        if params.get("demoDownstream.enabled", "false") != "false":
            raise RuntimeError("Downstream fixture must be disabled at baseline")
        # Require the opted-in fixture and trace-capable worker to be present in
        # the served source revision; an obsolete M5 image is insufficient.
        provenance = json.loads((ROOT / ".runtime/m6/acceptance/image-provenance.json").read_text())
        if provenance["demo"]["tag"] != self.state["worker_image"]:
            raise RuntimeError("Live worker is not the newly built M6 image")
        self.state["original_application"] = app
        return self.state

    def inject(self):
        self.state["injection_started_at"] = utc()
        values = {
            "demoDownstream.enabled": True,
            "demoDownstream.delayMs": 1000,
            "telemetry.enabled": True,
        }
        params = {
            p["name"]: p["value"]
            for p in self.state["original_application"]["spec"]["source"]["helm"]["parameters"]
        }
        params.update({k: str(v).lower() for k, v in values.items()})
        self.state["expected_parameters"] = [{"name": k, "value": v} for k, v in params.items()]
        self.checkpoint()
        self.env.configure_demo(values)
        return {
            "mechanism": "GitOps opt-in real 1000-ms internal HTTP fixture; worker timeout 400 ms",
            "delay_ms": 1000,
            "maximum_attempts_per_probe": 1,
        }

    def observe(self):
        until = time.monotonic() + 120
        while time.monotonic() < until:
            self.env.guard()
            raw = self.env.command(
                [
                    "get",
                    "deployment",
                    "demo-downstream",
                    "-n",
                    "opsproof-demo",
                    "--ignore-not-found",
                    "-o",
                    "json",
                ]
            )
            if not raw.strip():
                time.sleep(2)
                continue
            fixture = json.loads(raw)
            worker = self.env.get("deployment", "demo-worker")
            configured = {
                item["name"]: item.get("value")
                for item in worker["spec"]["template"]["spec"]["containers"][0].get("env", [])
            }
            if (
                fixture.get("status", {}).get("readyReplicas") == 1
                and configured.get("OPSPROOF_DOWNSTREAM_ENABLED") == "true"
                and worker["status"].get("observedGeneration") == worker["metadata"]["generation"]
                and worker["status"].get("updatedReplicas") == 1
                and worker["status"].get("readyReplicas") == 1
            ):
                break
            time.sleep(2)
        else:
            raise TimeoutError("Opted-in real dependency profile did not become Ready")
        self.job(50)
        time.sleep(2)
        logs = self.env.command(
            [
                "logs",
                "deployment/demo-worker",
                "-n",
                "opsproof-demo",
                "--since=30s",
                "--tail=100",
                "--timestamps",
            ]
        )
        self.state["observed"] = "M6 downstream failed" in logs
        self.env.save("downstream-timeout-log", {"log": logs})
        return {
            "hypothesis_observed": self.state["observed"],
            "timeout_log": logs,
            "recovery_attribution": "GitOps disable fixture + normal lease/fenced retry",
        }

    def cleanup(self):
        self.env.restore_demo(self.state["original_application"], self.state["expected_parameters"])
        original = self.state["original_application"]["spec"]["source"]["helm"]["parameters"]
        until = time.monotonic() + 120
        while time.monotonic() < until:
            app = self.env.get("application", "demo", "argocd")
            status = app.get("status", {})
            compared = status.get("sync", {}).get("comparedTo", {}).get("source", {})
            if (
                compared.get("helm", {}).get("parameters") == original
                and status.get("operationState", {}).get("phase") != "Running"
            ):
                break
            time.sleep(2)
        else:
            raise TimeoutError("Restored GitOps source has not reconciled")
        # This project's GitOps policy deliberately disables automatic pruning.
        # Remove only this trial's two named fixture resources, after source
        # restoration, with server-enforced identity/version preconditions.
        for kind, group, plural, tracking in (
            ("deployment", "/apis/apps/v1", "deployments", "apps/Deployment"),
            ("service", "/api/v1", "services", "/Service"),
        ):
            raw = self.env.command(
                [
                    "get",
                    kind,
                    "demo-downstream",
                    "-n",
                    "opsproof-demo",
                    "--ignore-not-found",
                    "-o",
                    "json",
                ]
            )
            if not raw.strip():
                continue
            resource = json.loads(raw)
            metadata = resource["metadata"]
            if metadata.get("annotations", {}).get(
                "argocd.argoproj.io/tracking-id"
            ) != f"demo:{tracking}:opsproof-demo/demo-downstream" or datetime.fromisoformat(
                metadata["creationTimestamp"].replace("Z", "+00:00")
            ) < datetime.fromisoformat(self.state["injection_started_at"]):
                raise RuntimeError("Fixture ownership differs from this trial; deletion refused")
            self.env.save(
                "fixture-cleanup-identity",
                {
                    "kind": kind,
                    "uid": metadata["uid"],
                    "resource_version": metadata["resourceVersion"],
                },
            )
            self.env.command(
                [
                    "delete",
                    "--raw",
                    f"{group}/namespaces/opsproof-demo/{plural}/demo-downstream",
                    "-f",
                    "-",
                ],
                input=json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "DeleteOptions",
                        "preconditions": {
                            "uid": metadata["uid"],
                            "resourceVersion": metadata["resourceVersion"],
                        },
                    }
                ),
            )
        while time.monotonic() < until:
            app = self.env.get("application", "demo", "argocd")
            if (
                app.get("status", {}).get("sync", {}).get("status") == "Synced"
                and app.get("status", {}).get("health", {}).get("status") == "Healthy"
            ):
                break
            time.sleep(2)
        else:
            raise TimeoutError("Restored application did not return Synced/Healthy")
        return {
            "profile_restore_requested": True,
            "jobs": self.wait_jobs(180, guard=False),
        }


class MisleadingEvidence(Adapter):
    scenario = "misleading_evidence"
    target_resource = ("deployment", "prometheus", "opsproof-observability")

    def inject(self):
        self.state["injection_started_at"] = utc()
        self.env.stop_forward("prometheus")
        self.state["observer_interrupted"] = True
        return {
            "mechanism": "terminate only the owned Prometheus observer connection",
            "application_data_mutated": False,
            "telemetry_server_still_running": True,
        }

    def observe(self):
        for _ in range(6):
            self.env.guard()
            time.sleep(0.5)
        absent = False
        try:
            http(
                19090,
                "/api/v1/query?" + urlencode({"query": 'up{job="opsproof-demo-api"}'}),
            )
        except OSError:
            absent = True
        facts = Observation(
            observed_at=datetime.now(UTC),
            target="opsproof-demo",
            metrics_fresh=not absent,
            collection_errors=["Actual local Prometheus observer disconnected"] if absent else [],
        )
        baseline = deterministic_m6(facts)
        contradictory = facts.model_copy(
            update={"metrics_fresh": True, "contradictions": ["Sources disagree"]}
        )
        stale = facts.model_copy(update={"observed_at": datetime(2020, 1, 1, tzinfo=UTC)})
        results = [baseline, deterministic_m6(contradictory), deterministic_m6(stale)]
        self.state["observed"] = absent and all(r.abstained and r.action == "none" for r in results)
        return {
            "hypothesis_observed": self.state["observed"],
            "actual_observation": facts.model_dump(mode="json"),
            "findings": [r.model_dump() for r in results],
            "additional_variants": "explicit controlled replay",
            "recovery_attribution": "restore owned observer; no workload action authorized",
        }

    def cleanup(self):
        if "prometheus" not in self.env.forwards:
            self.env.start_forward("prometheus")
        return {
            "observer_restored": http(19090, "/-/ready")[0] == 200,
            "workload_ready": http(18088, "/health/ready")[0] == 200,
        }


ADAPTERS = {
    adapter.scenario: adapter
    for adapter in (
        Saturation,
        FaultyRelease,
        DatabaseConnectivity,
        WorkerFailure,
        DownstreamLatency,
        MisleadingEvidence,
    )
}
