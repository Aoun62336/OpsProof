"""Boot final images in isolated, nonroot, read-only, networkless containers.

Verifies HTTP liveness/auth, honest unavailable-dependency readiness and static
web serving. These are container smoke checks, not live Kubernetes fault proof.
"""

import json
import subprocess
import time
from uuid import uuid4

from scripts.m5.preflight import ROOT
from scripts.m6.local_environment import write_json

PROBE = r"""
import json,os,urllib.request,urllib.error
results={"uid":os.getuid(),"responses":{}}
for path in ("/health/live","/health/ready","/api/v1/m6/trials"):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080"+path,timeout=10) as response:
            results["responses"][path]={"status":response.status,"body":response.read(500).decode()}
    except urllib.error.HTTPError as error:
        results["responses"][path]={"status":error.code}
print(json.dumps(results))
"""


def main():
    images = json.loads((ROOT / ".runtime/m6/acceptance/image-provenance.json").read_text())
    output = ROOT / ".runtime/m6/acceptance/images" / ("smoke-" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    records = {}
    for component in ("demo", "control", "web"):
        image = images[component]
        identifier = None
        record = {
            "image_id": image["local_image_id"],
            "passed": False,
            "cleanup_verified": False,
        }
        args = [
            "docker",
            "run",
            "--rm",
            "-d",
            "--read-only",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "256m",
            "--cpus",
            "0.5",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=33554432",
            "--label",
            "opsproof.io/m6-smoke=true",
        ]
        if component == "web":
            args += [
                "--add-host",
                "control-api.opsproof-control.svc.cluster.local:127.0.0.1",
            ]
        else:
            prefix = "OPSPROOF_CONTROL_" if component == "control" else "OPSPROOF_"
            args += [
                "-e",
                prefix + "DATABASE_URL=postgresql://127.0.0.1:5999/unavailable",
                "-e",
                prefix + "REDIS_URL=redis://127.0.0.1:6399",
            ]
        try:
            identifier = subprocess.check_output(
                [*args, image["local_image_id"]], text=True, timeout=30
            ).strip()
            for _ in range(30):
                if component == "web":
                    ready = subprocess.run(
                        [
                            "docker",
                            "exec",
                            identifier,
                            "wget",
                            "-qO-",
                            "http://127.0.0.1:8080/",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                else:
                    ready = subprocess.run(
                        [
                            "docker",
                            "exec",
                            identifier,
                            "python",
                            "-c",
                            "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live',timeout=1)",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                if ready.returncode == 0:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError("Image service did not start in its bounded environment")
            if component == "web":
                record["static_index_served"] = '<div id="root">' in ready.stdout
                uid = subprocess.check_output(
                    ["docker", "exec", identifier, "id", "-u"], text=True
                ).strip()
                record["uid"] = int(uid)
                record["passed"] = record["static_index_served"] and record["uid"] != 0
            else:
                probe = subprocess.run(
                    ["docker", "exec", "-i", identifier, "python", "-"],
                    input=PROBE,
                    capture_output=True,
                    text=True,
                    timeout=25,
                    check=True,
                )
                result = json.loads(probe.stdout)
                record.update(result)
                codes = result["responses"]
                record["passed"] = (
                    result["uid"] != 0
                    and codes["/health/live"]["status"] == 200
                    and codes["/health/ready"]["status"] == 503
                )
                if component == "control":
                    record["passed"] &= codes["/api/v1/m6/trials"]["status"] == 401
            log = subprocess.check_output(
                ["docker", "logs", identifier],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=10,
            )
            (output / (component + ".log")).write_text(log, encoding="utf-8")
        except Exception as exc:
            record["error_type"] = type(exc).__name__
        finally:
            if identifier:
                label = subprocess.check_output(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        '{{index .Config.Labels "opsproof.io/m6-smoke"}}',
                        identifier,
                    ],
                    text=True,
                ).strip()
                if label != "true":
                    raise RuntimeError("Refusing to stop an unowned smoke container")
                subprocess.run(
                    ["docker", "stop", "--time", "10", identifier],
                    check=True,
                    capture_output=True,
                    timeout=20,
                )
                remaining = subprocess.check_output(
                    [
                        "docker",
                        "ps",
                        "-a",
                        "--filter",
                        "id=" + identifier,
                        "--format",
                        "{{.ID}}",
                    ],
                    text=True,
                ).strip()
                record["cleanup_verified"] = not remaining
        records[component] = record
        write_json(output / (component + ".json"), record)
        print(component, "PASS" if record["passed"] else "FAIL", flush=True)
    write_json(output / "result.json", records)
    return 0 if all(r["passed"] and r["cleanup_verified"] for r in records.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
