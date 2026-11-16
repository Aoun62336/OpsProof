"""Render M5 and M6 positive/negative profiles without contacting a cluster."""

import json
import subprocess
from pathlib import Path

import yaml

from scripts.platform.validate_charts import validate

ROOT = Path(__file__).resolve().parents[2]
CHART = "infra/helm/opsproof-services"


def main():
    output = ROOT / ".runtime/m6/acceptance/helm"
    output.mkdir(parents=True, exist_ok=True)
    results = []
    profiles = [
        ("control-default", "control", {}, None),
        ("demo-default", "demo", {}, None),
        (
            "control-ledger",
            "control",
            {"m6.enabled": "true", "m6.trialWorkerEnabled": "true"},
            None,
        ),
        (
            "control-recovery-ledger",
            "control",
            {
                "m6.enabled": "true",
                "m6.trialWorkerEnabled": "true",
                "kubernetesRecoveryEnabled": "true",
            },
            None,
        ),
        (
            "demo-downstream",
            "demo",
            {
                "demoDownstream.enabled": "true",
                "demoDownstream.delayMs": "1000",
                "telemetry.enabled": "true",
            },
            None,
        ),
        (
            "worker-disabled-ledger",
            "control",
            {"m6.trialWorkerEnabled": "true"},
            "enabled control component",
        ),
        (
            "arming-without-worker",
            "control",
            {"m6.armEnabled": "true"},
            "dedicated trial worker",
        ),
        (
            "demo-ledger-denied",
            "demo",
            {"m6.enabled": "true"},
            "only valid for control",
        ),
        (
            "control-fixture-denied",
            "control",
            {"demoDownstream.enabled": "true"},
            "only valid for demo",
        ),
        (
            "delay-too-large",
            "demo",
            {"demoDownstream.enabled": "true", "demoDownstream.delayMs": "2001"},
            "maximum",
        ),
        (
            "delay-negative",
            "demo",
            {"demoDownstream.enabled": "true", "demoDownstream.delayMs": "-1"},
            "minimum",
        ),
        ("bool-string", "control", {"m6.enabled": "STRING:false"}, "boolean"),
        (
            "rollout-hpa",
            "demo",
            {
                "rollout.enabled": "true",
                "rollout.image": "opsproof-demo:healthy",
                "autoscaling.hpa.enabled": "true",
                "autoscaling.hpa.rolloutTargetEnabled": "true",
            },
            None,
        ),
        (
            "rollout-hpa-not-opted-in",
            "demo",
            {
                "rollout.enabled": "true",
                "rollout.image": "opsproof-demo:healthy",
                "autoscaling.hpa.enabled": "true",
            },
            "ownership cutover",
        ),
        (
            "rollout-target-without-rollout",
            "demo",
            {
                "autoscaling.hpa.enabled": "true",
                "autoscaling.hpa.rolloutTargetEnabled": "true",
            },
            "requires demo Rollout",
        ),
        (
            "control-reuse",
            "control",
            {"m6.enabled": "true", "m6.reuseEnabled": "true"},
            None,
        ),
        (
            "reuse-without-ledger",
            "control",
            {"m6.reuseEnabled": "true"},
            "requires enabled ledger",
        ),
    ]
    profiles.append(
        (
            "ledger-without-restricted-secret",
            "control",
            {"m6.enabled": "true"},
            "requires restricted runtime secret",
        )
    )
    profiles += [
        ("demo-fresh-probe", "demo", {"m6DependencyProbeEnabled": "true"}, None),
        (
            "control-fresh-probe-denied",
            "control",
            {"m6DependencyProbeEnabled": "true"},
            "only valid for demo",
        ),
        (
            "m6-ai-forbidden",
            "control",
            {"m6.enabled": "true", "aiEnabled": "true"},
            "does not permit model calls",
        ),
    ]
    for label, component, values, rejection in profiles:
        if (
            values.get("m6.enabled") == "true"
            and component == "control"
            and label != "ledger-without-restricted-secret"
        ):
            values = {**values, "m6.runtimeSecretName": "opsproof-control-m6-runtime"}
        args = [
            "helm",
            "template",
            component,
            CHART,
            "-f",
            f"{CHART}/values-{component}.yaml",
            "--set-string",
            "image.tag=m6-render-only",
        ]
        for key, value in values.items():
            args += [
                "--set-string" if value.startswith("STRING:") else "--set",
                f"{key}={value.removeprefix('STRING:')}",
            ]
        run = subprocess.run(
            args, cwd=ROOT, capture_output=True, text=True, timeout=30, check=False
        )
        (output / f"{label}.yaml").write_text(run.stdout, encoding="utf-8")
        (output / f"{label}.log").write_text(run.stderr, encoding="utf-8")
        if rejection:
            assert run.returncode != 0 and rejection.lower() in run.stderr.lower(), label
            results.append({"profile": label, "passed": True, "expected_rejection": rejection})
            continue
        assert run.returncode == 0, run.stderr
        objects = [obj for obj in yaml.safe_load_all(run.stdout) if obj]
        validate(objects)
        if label == "rollout-hpa":
            hpa = next(o for o in objects if o["kind"] == "HorizontalPodAutoscaler")
            assert hpa["spec"]["scaleTargetRef"] == {
                "apiVersion": "argoproj.io/v1alpha1",
                "kind": "Rollout",
                "name": "demo-api",
            }
            rollout = next(o for o in objects if o["kind"] == "Rollout")
            assert "replicas" not in rollout["spec"]
            assert not any(
                o["kind"] == "Deployment" and o["metadata"]["name"] == "demo-api" for o in objects
            )
        trial = next(
            (
                o
                for o in objects
                if o["kind"] == "Deployment" and o["metadata"]["name"] == "control-trial"
            ),
            None,
        )
        assert bool(trial) == (values.get("m6.trialWorkerEnabled") == "true")
        if trial:
            spec = trial["spec"]["template"]["spec"]
            assert spec["automountServiceAccountToken"] is False
            assert not any("projected" in volume for volume in spec.get("volumes", []))
            refs = spec["containers"][0]["envFrom"]
            assert refs == [
                {"secretRef": {"name": "opsproof-control-runtime"}},
                {"secretRef": {"name": "opsproof-control-m6-runtime"}},
            ]
            env = {item["name"]: item.get("value") for item in spec["containers"][0]["env"]}
            assert env["OPSPROOF_CONTROL_M6_ARM_ENABLED"] == "false"
            assert env["OPSPROOF_CONTROL_KUBERNETES_RECOVERY_ENABLED"] == "false"
            assert env["OPSPROOF_CONTROL_AI_ENABLED"] == "false"
        results.append({"profile": label, "passed": True, "objects": len(objects)})
    for label, flags, rejection in [
        ("reuse-new-namespace", [], None),
        ("reuse-existing-namespace", ["--set", "createNamespace=false"], None),
        ("reuse-invalid-delay", ["--set", "fixture.delayMs=2001"], "maximum"),
        (
            "reuse-invalid-namespace-type",
            ["--set-string", "createNamespace=false"],
            "boolean",
        ),
    ]:
        run = subprocess.run(
            [
                "helm",
                "template",
                "opsproof-reuse",
                "infra/helm/opsproof-reuse",
                "--set-string",
                "image.repository=opsproof-demo,image.tag=m6-render-only",
                *flags,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        (output / f"{label}.yaml").write_text(run.stdout, encoding="utf-8")
        (output / f"{label}.log").write_text(run.stderr, encoding="utf-8")
        if rejection:
            assert run.returncode != 0 and rejection in run.stderr.lower(), label
        else:
            assert run.returncode == 0, run.stderr
            objects = [item for item in yaml.safe_load_all(run.stdout) if item]
            validate(objects)
            assert all(
                item["metadata"].get("namespace")
                in (None, "opsproof-control", "opsproof-reuse-test")
                for item in objects
            )
            assert sum(item["kind"] == "Namespace" for item in objects) == (
                label == "reuse-new-namespace"
            )
        results.append({"profile": label, "passed": True, "expected_rejection": rejection})
    (output / "result.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len(results)} M6 Helm positive/negative profiles; no deployment")


if __name__ == "__main__":
    main()
