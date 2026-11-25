"""Validate all three Terraform roots using isolated external tool data; no apply.

Every test uses the committed mock provider. No state backend or real AWS account
is initialized. Real deployment uses separately reviewed owner backend settings.
"""

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime

from scripts.paths import ROOT, cache, local_root

MODULES = ("state-bootstrap", "platform", "public-edge")


def data_directory(module: str):
    if module not in MODULES:
        raise ValueError("Unknown Terraform root")
    identity = hashlib.sha256(ROOT.as_posix().lower().encode()).hexdigest()[:12]
    return local_root() / "terraform/validation" / identity / module


def main() -> int:
    output = ROOT / ".runtime/verification/infrastructure"
    output.mkdir(parents=True, exist_ok=True)
    plugin_cache = cache("terraform")
    plugin_cache.mkdir(parents=True, exist_ok=True)
    records = []
    for module in MODULES:
        directory = data_directory(module)
        directory.mkdir(parents=True, exist_ok=True)
        env = {key: value for key, value in os.environ.items() if not key.startswith("AWS_")}
        env.update(
            TF_DATA_DIR=str(directory),
            TF_PLUGIN_CACHE_DIR=str(plugin_cache),
            AWS_EC2_METADATA_DISABLED="true",
            CHECKPOINT_DISABLE="1",
        )
        for arguments in (
            ["fmt", "-check", "-recursive"],
            ["init", "-backend=false", "-input=false", "-lockfile=readonly", "-no-color"],
            ["validate", "-no-color"],
            ["test", "-no-color"],
        ):
            command = ["terraform", "-chdir=infra/terraform/" + module, *arguments]
            result = subprocess.run(
                command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300
            )
            name = module + "-" + arguments[0] + ".log"
            (output / name).write_text(result.stdout + result.stderr, encoding="utf-8")
            records.append({"root": module, "command": command, "exit_code": result.returncode})
            print(module, arguments[0], "PASS" if result.returncode == 0 else "FAIL", flush=True)
            if result.returncode:
                break
        if result.returncode:
            break
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "passed": len(records) == 12 and all(row["exit_code"] == 0 for row in records),
        "terraform_apply": False,
        "real_aws_calls": 0,
        "results": records,
    }
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
