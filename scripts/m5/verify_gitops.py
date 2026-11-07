"""Observe real source revision, harmless drift repair, and source-error recovery."""

import json
import subprocess
import time
from datetime import UTC, datetime

from local_cluster import kubectl_prefix
from preflight import ROOT


def main():
    kube = kubectl_prefix()

    def get(kind, name, ns):
        return json.loads(
            subprocess.check_output(
                [*kube, "get", kind, name, "-n", ns, "-o", "json"], text=True
            )
        )

    def patch(kind, name, ns, body):
        path = ROOT / ".runtime/m5/gitops-trial-patch.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        subprocess.run(
            [
                *kube,
                "patch",
                kind,
                name,
                "-n",
                ns,
                "--type=merge",
                "--patch-file",
                str(path),
            ],
            text=True,
            check=True,
        )

    def wait(predicate, description):
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(2)
        raise RuntimeError("Deadline: " + description)

    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    initial = get("application", "web", "argocd")
    previous = initial["status"]["sync"]["revision"]
    if revision == previous:
        raise RuntimeError("Commit a real releaseMarker change before this trial")
    before_marker = get("deployment", "opsproof-web", "opsproof-ui")["metadata"][
        "annotations"
    ]["opsproof.io/release-marker"]
    patch(
        "application",
        "web",
        "argocd",
        {"spec": {"source": {"targetRevision": revision}}},
    )

    def synced():
        app = get("application", "web", "argocd")
        status = app.get("status", {})
        if (
            status.get("sync", {}).get("revision") == revision
            and status["sync"].get("status") == "Synced"
            and status.get("health", {}).get("status") == "Healthy"
        ):
            return app
        return None

    current = wait(synced, "new Git revision synced")
    after_marker = get("deployment", "opsproof-web", "opsproof-ui")["metadata"][
        "annotations"
    ]["opsproof.io/release-marker"]
    if before_marker == after_marker:
        raise RuntimeError(
            "Git revision changed without the declared live marker change"
        )
    patch(
        "deployment",
        "opsproof-web",
        "opsproof-ui",
        {
            "metadata": {
                "annotations": {"opsproof.io/release-marker": "intentional-m5-drift"}
            }
        },
    )
    observed_drift = get("deployment", "opsproof-web", "opsproof-ui")["metadata"][
        "annotations"
    ]["opsproof.io/release-marker"]
    if observed_drift != "intentional-m5-drift":
        raise RuntimeError("Drift was not observed; repeat trial")
    wait(
        lambda: (
            get("deployment", "opsproof-web", "opsproof-ui")["metadata"][
                "annotations"
            ].get("opsproof.io/release-marker")
            == after_marker
        ),
        "Argo self-healed annotation",
    )
    repaired = wait(synced, "healthy after drift correction")
    original_path = current["spec"]["source"]["path"]
    failure = None
    try:
        patch(
            "application",
            "web",
            "argocd",
            {"spec": {"source": {"path": "infra/does-not-exist-m5-trial"}}},
        )

        def comparison_error():
            conditions = (
                get("application", "web", "argocd")
                .get("status", {})
                .get("conditions", [])
            )
            return next(
                (
                    condition
                    for condition in conditions
                    if condition["type"] == "ComparisonError"
                ),
                None,
            )

        failure = wait(comparison_error, "source error surfaced")
    finally:
        patch(
            "application",
            "web",
            "argocd",
            {"spec": {"source": {"path": original_path}}},
        )
    final = wait(synced, "recovery after source error")
    record = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "passed": True,
        "repository": current["spec"]["source"]["repoURL"],
        "previous_revision": previous,
        "new_revision": revision,
        "marker_before": before_marker,
        "marker_after": after_marker,
        "observed_drift": observed_drift,
        "reconciled_marker": after_marker,
        "drift_operation": repaired["status"].get("operationState"),
        "observed_source_error": failure,
        "final_status": final["status"],
        "scope": "local-only Git; no GitHub publication",
    }
    (ROOT / ".runtime/m5/acceptance/gitops-trial.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    print("PASS: real Git change, observed drift correction and source-error recovery")


if __name__ == "__main__":
    main()
