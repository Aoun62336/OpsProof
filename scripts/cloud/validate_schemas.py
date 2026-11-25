"""Validate cloud renders against built-in and locked-controller CRD schemas.

No cluster access. CRD CEL rules, webhook admission and runtime compatibility
still require the owner deployment checks. No missing schemas are ignored.
"""

import hashlib
import json
import subprocess
from urllib.request import urlopen
from uuid import uuid4

import yaml

from scripts.paths import ROOT, cache
from scripts.security_tools import binary

OPENAPI_URL = (
    "https://raw.githubusercontent.com/kubernetes/kubernetes/v1.35.0/api/openapi-spec/swagger.json"
)
SCHEMA_SHA256 = "483500149ee52ce5753d75f5639101d985bb4f5e902cc05b1ba7627465d62446"


def crd_definition_schema():
    """Use the official versioned API schema absent from the default registry."""
    path = cache("kubernetes", "v1.35.0", "swagger.json")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(OPENAPI_URL, timeout=60) as response:
            path.write_bytes(response.read(12_000_000))
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SCHEMA_SHA256:
        raise ValueError("Official Kubernetes OpenAPI checksum differs from reviewed pin")
    definitions = json.loads(data)["definitions"]
    name = "io.k8s.apiextensions-apiserver.pkg.apis.apiextensions.v1.CustomResourceDefinition"
    needed = {}

    def collect(value):
        if isinstance(value, dict):
            reference = value.get("$ref", "")
            if isinstance(reference, str) and reference.startswith("#/definitions/"):
                key = reference.removeprefix("#/definitions/")
                if key not in needed:
                    needed[key] = definitions[key]
                    collect(needed[key])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    reference = {"$ref": "#/definitions/" + name}
    collect(reference)
    return {**reference, "definitions": needed}


def schemas(documents):
    result = {}
    for document in documents:
        if document.get("kind") != "CustomResourceDefinition":
            continue
        spec = document["spec"]
        for version in spec["versions"]:
            if not version.get("served"):
                continue
            schema = version["schema"]["openAPIV3Schema"]
            key = (spec["group"], spec["names"]["kind"].lower(), version["name"])
            if key in result and result[key] != schema:
                raise ValueError("Conflicting custom-resource schemas")
            result[key] = schema
    return result


def main():
    renders = ROOT / ".runtime/verification/cloud/helm"
    source = max(
        (p for p in renders.iterdir() if (p / "result.json").is_file()),
        key=lambda p: (p / "result.json").stat().st_mtime_ns,
    )
    output = ROOT / ".runtime/verification/cloud/schemas" / uuid4().hex
    output.mkdir(parents=True)
    documents = [
        doc
        for path in sorted(source.glob("*.yaml"))
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if doc
    ]
    # Helm may emit a Kubernetes List containing resources from multiple groups.
    documents = [
        item for doc in documents for item in (doc["items"] if doc.get("kind") == "List" else [doc])
    ]
    registry = schemas(documents)
    if not registry:
        raise ValueError("Controller renders contain no CRD schemas; include CRDs")
    registry[("apiextensions.k8s.io", "customresourcedefinition", "v1")] = crd_definition_schema()
    filenames = set()
    for (group, kind, version), schema in registry.items():
        # Kubeconform normalizes built-in group names differently from custom
        # groups. A collision-checked flat registry avoids ambiguous aliases.
        filename = f"{kind}_{version}.json"
        if filename in filenames:
            raise ValueError("Ambiguous custom-resource kind/version schema")
        filenames.add(filename)
        schema = json.loads(json.dumps(schema))
        definition = schema
        if "$ref" in schema:
            definition = schema["definitions"][schema["$ref"].removeprefix("#/definitions/")]
        definition["properties"]["apiVersion"] = {"enum": [f"{group}/{version}"]}
        target = output / "schemas" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(schema), encoding="utf-8")
    args = [
        str(binary("kubeconform")),
        "-strict",
        "-summary",
        "-output",
        "json",
        "-kubernetes-version",
        "1.35.0",
    ]
    groups = {}
    for document in documents:
        api = document["apiVersion"].rsplit("/", 1)
        key = (api[0], document["kind"].lower(), api[1]) if len(api) == 2 else None
        schema = f"{key[1]}_{key[2]}.json" if key in registry else "builtins"
        groups.setdefault(schema, []).append(document)
    checks = []
    for name, rows in groups.items():
        manifest = output / (name + ".yaml")
        manifest.write_text(yaml.safe_dump_all(rows), encoding="utf-8")
        location = "default" if name == "builtins" else str(output / "schemas" / name)
        run = subprocess.run(
            [*args, "-schema-location", location, str(manifest)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        (output / (name + "-validation.json")).write_text(run.stdout, encoding="utf-8")
        (output / (name + ".log")).write_text(run.stderr, encoding="utf-8")
        checks.append({"schema": name, "objects": len(rows), "exit_code": run.returncode})
    report = {
        "passed": all(row["exit_code"] == 0 for row in checks),
        "checks": checks,
        "source": source.relative_to(ROOT).as_posix(),
        "objects": len(documents),
        "custom_schemas": len(registry),
        "cluster_access": False,
        "missing_schemas_ignored": False,
        "limits": "Structural schemas only; CEL/admission/runtime require live acceptance",
    }
    # Prove a custom schema actually rejects an invalid typed field.
    custom = next((doc for doc in documents if doc.get("kind") == "ScaledObject"), None)
    if custom is None:
        raise ValueError("Expected the cloud queue scaler to exercise a custom schema")
    custom["spec"]["pollingInterval"] = "invalid-number"
    negative = output / "negative.yaml"
    negative.write_text(yaml.safe_dump(custom), encoding="utf-8")
    reject = subprocess.run(
        [
            *args,
            "-schema-location",
            str(output / "schemas/scaledobject_v1alpha1.json"),
            str(negative),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    (output / "negative.json").write_text(reject.stdout, encoding="utf-8")
    report["invalid_custom_resource_rejected"] = (
        reject.returncode != 0
        and "/spec/pollingInterval" in reject.stdout
        and "want integer" in reject.stdout
    )
    report["passed"] = report["passed"] and report["invalid_custom_resource_rejected"]
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
