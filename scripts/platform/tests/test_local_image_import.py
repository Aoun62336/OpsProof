"""Refuse unrelated nodes or unreviewed artifacts before image-store mutation."""

import hashlib
import json

import pytest

from scripts.platform.import_local_image import configuration_digest, import_image


def test_manifest_and_configuration_identities_are_verified_separately():
    raw = json.dumps({"config": {"digest": "sha256:" + "a" * 64}}).encode()
    platform = {
        "Descriptor": {
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        }
    }
    assert configuration_digest(platform, raw) == "sha256:" + "a" * 64
    with pytest.raises(ValueError):
        configuration_digest(platform, raw + b" ")
    platform["Descriptor"]["mediaType"] = "application/vnd.oci.image.index.v1+json"
    with pytest.raises(ValueError):
        configuration_digest(platform, raw)


@pytest.mark.parametrize(
    "cluster,digest",
    [
        ("production", "sha256:" + "a" * 64),
        ("opsproof-monitoring-user", "sha256:" + "a" * 64),
        ("opsproof", "sha256:short"),
    ],
)
def test_invalid_scope_never_contacts_docker(monkeypatch, cluster, digest):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Invalid scope must be rejected before Docker access")

    monkeypatch.setattr("subprocess.check_output", forbidden)
    with pytest.raises(ValueError):
        import_image("fixture:local", digest, cluster)


@pytest.mark.parametrize(
    "owner,identity,platform",
    [
        ("unrelated", "a", "amd64"),
        ("opsproof", "b", "amd64"),
        ("opsproof", "a", "arm64"),
    ],
)
def test_unowned_node_or_wrong_image_cannot_mutate_runtime(monkeypatch, owner, identity, platform):
    def inspect(args, **_kwargs):
        if args[1] == "inspect":
            return json.dumps([{"Config": {"Labels": {"k3d.cluster": owner}}}])
        return json.dumps(
            [{"Id": "sha256:" + identity * 64, "Os": "linux", "Architecture": platform}]
        )

    def forbidden(*_args, **_kwargs):
        pytest.fail("Unreviewed image or node must not start an import")

    monkeypatch.setattr("subprocess.check_output", inspect)
    monkeypatch.setattr("subprocess.Popen", forbidden)
    with pytest.raises(ValueError):
        import_image("fixture:local", "sha256:" + "a" * 64, "opsproof")
