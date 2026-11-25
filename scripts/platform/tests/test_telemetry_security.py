from copy import deepcopy

import pytest

from scripts.platform import telemetry_security as policy
from scripts.platform.scan_telemetry import SCRATCH_COLLECTOR, require_inventory


@pytest.mark.parametrize("family", [None, "none", "unknown", ""])
def test_unsupported_os_inventory_cannot_be_presented_as_a_clean_scan(family):
    with pytest.raises(RuntimeError):
        require_inventory(
            {
                "Metadata": {"OS": {"Family": family}},
                "Results": [{"Class": "lang-pkgs", "Packages": [{"Name": "go"}]}],
            }
        )


def test_supported_os_requires_actual_packages():
    with pytest.raises(RuntimeError):
        require_inventory({"Metadata": {"OS": {"Family": "wolfi"}}, "Results": []})
    require_inventory(
        {
            "Metadata": {"OS": {"Family": "wolfi"}},
            "Results": [{"Class": "os-pkgs", "Packages": [{"Name": "glibc"}]}],
        }
    )


def test_only_exact_official_scratch_image_can_have_no_os_packages():
    data = {
        "Metadata": {"RepoDigests": [SCRATCH_COLLECTOR]},
        "Results": [
            {"Type": "gobinary", "Target": "otelcol-contrib", "Packages": [{"Name": "go"}]}
        ],
    }
    require_inventory(data, SCRATCH_COLLECTOR)
    with pytest.raises(RuntimeError):
        require_inventory(data, "another-scratch-image")
    data["Results"] = []
    with pytest.raises(RuntimeError):
        require_inventory(data, SCRATCH_COLLECTOR)


def report():
    return {
        "Metadata": {"RepoDigests": [policy.IMAGE]},
        "Results": [
            {
                "Target": policy.TARGET,
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": cve,
                        "PkgName": policy.MODULE,
                        "InstalledVersion": policy.VERSION,
                        "PkgIdentifier": {
                            "PURL": "pkg:golang/" + policy.MODULE + "@" + policy.VERSION
                        },
                    }
                    for cve in policy.FIXES
                ],
            }
        ],
    }


def proven(fix):
    return {
        "status": "ahead",
        "base": fix,
        "merge_base": fix,
        "behind_by": 0,
        "head": policy.REVISION,
    }


def test_built_artifact_is_bound_to_the_exact_patched_source_and_supported_os():
    data = report()
    image = "sha256:" + "a" * 64
    data["Metadata"] = {
        "ImageID": image,
        "OS": {"Family": "wolfi"},
        "ImageConfig": {"config": {"Labels": {"org.opsproof.grafana-source": policy.IMAGE}}},
    }
    document, _ = policy.verified_fixed(data, image, compare=proven)
    assert len(document["statements"]) == 2
    data["Metadata"]["ImageConfig"]["config"]["Labels"]["org.opsproof.grafana-source"] = (
        "another-source"
    )
    with pytest.raises(ValueError):
        policy.verified_fixed(data, image, compare=proven)


def test_only_source_proven_fixes_receive_fixed_status():
    data = report()
    data["Results"][0]["Vulnerabilities"].append({"VulnerabilityID": "NEW-HIGH"})
    document, receipts = policy.verified_fixed(data, policy.IMAGE, compare=proven)
    assert len(document["statements"]) == 2
    assert set(receipts) == set(policy.FIXES)
    assert {s["status"] for s in document["statements"]} == {"fixed"}
    assert all(s["vulnerability"]["name"] != "NEW-HIGH" for s in document["statements"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("PkgName", "another/library"),
        ("InstalledVersion", "v1.0.0"),
        ("PkgIdentifier", {"PURL": "wrong"}),
    ],
)
def test_changed_component_has_no_resolution(field, value):
    data = report()
    data["Results"][0]["Vulnerabilities"][0][field] = value
    with pytest.raises(ValueError):
        policy.verified_fixed(data, policy.IMAGE, compare=proven)


@pytest.mark.parametrize(
    "field,value",
    [("head", "0" * 40), ("status", "diverged"), ("behind_by", 1), ("merge_base", "0" * 40)],
)
def test_missing_or_wrong_ancestry_fails_closed(field, value):
    def incorrect(fix):
        proof = proven(fix)
        proof[field] = value
        return proof

    with pytest.raises(ValueError):
        policy.verified_fixed(report(), policy.IMAGE, compare=incorrect)


def test_other_image_and_unavailable_proof_cannot_pass():
    with pytest.raises(ValueError):
        policy.verified_fixed(report(), "another/image@sha256:" + "0" * 64, compare=proven)
    data = deepcopy(report())
    data["Metadata"]["RepoDigests"] = []
    with pytest.raises(ValueError):
        policy.verified_fixed(data, policy.IMAGE, compare=proven)

    def offline(_):
        raise TimeoutError()

    with pytest.raises(TimeoutError):
        policy.verified_fixed(report(), policy.IMAGE, compare=offline)
