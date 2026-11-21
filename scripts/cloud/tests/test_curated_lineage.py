"""Public case lineage cannot be established by a fabricated hex digest alone."""

import hashlib
import json

import pytest

from scripts import paths
from scripts.cloud import verify_curated_evidence as lineage
from scripts.cloud.build_public_replay import CASES
from scripts.cloud.verify_curated_evidence import verify


def fixtures(root):
    cases, bindings = [], {}
    for scenario in sorted(CASES):
        directory = root / ".runtime/reliability/trials" / scenario
        directory.mkdir(parents=True)
        source = {"head": "a" * 40, "tree_sha256": "b" * 64, "dirty": True}
        result = {"status": "SUCCEEDED", "scenario": scenario}
        proof = {
            "cleanup_verified": True,
            "hypothesis_verified": True,
            "verification_receipt": {
                "checks": {
                    key: True
                    for key in (
                        "current_health",
                        "exact_jobs",
                        "original_configuration",
                        "observer_identity",
                    )
                }
            },
        }
        for name, value in (
            ("source.json", source),
            ("result.json", result),
            ("independent-result.json", proof),
        ):
            (directory / name).write_text(json.dumps(value), encoding="utf-8")
        case = {
            "id": scenario.replace("_", "-"),
            "scenario": scenario,
            "title": "Offline test fixture",
            "environment": "local-k3d",
            "source_commit": source["head"],
            "source_tree_sha256": source["tree_sha256"],
            "source_dirty": True,
            "status": "succeeded",
            "observed_utc": "2026-11-01T00:00:00Z",
            "summary": "Test fixture only",
            "findings": ["Fixture observation"],
            "limitations": "No real acceptance claim",
            "source_evidence_sha256": hashlib.sha256(
                (directory / "independent-result.json").read_bytes()
            ).hexdigest(),
        }
        cases.append(case)
        bindings[case["id"]] = directory.relative_to(root).as_posix()
    return cases, bindings


def test_complete_lineage_requires_public_review(tmp_path):
    cases, bindings = fixtures(tmp_path)
    assert (
        verify(cases, bindings, root=tmp_path)["status"]
        == "PRIVATE_LINEAGE_VERIFIED_PUBLIC_REVIEW_REQUIRED"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_evidence_sha256", "c" * 64),
        ("source_tree_sha256", "c" * 64),
        ("source_dirty", False),
        ("environment", "temporary-eks"),
    ],
)
def test_public_identity_or_environment_cannot_be_relabelled(tmp_path, field, value):
    cases, bindings = fixtures(tmp_path)
    cases[0][field] = value
    with pytest.raises(ValueError):
        verify(cases, bindings, root=tmp_path)


def test_binding_cannot_escape_private_trial_directory(tmp_path):
    cases, bindings = fixtures(tmp_path)
    bindings[cases[0]["id"]] = "../../outside"
    with pytest.raises(ValueError):
        verify(cases, bindings, root=tmp_path)


def test_archived_lineage_remains_valid_when_new_trials_exist(tmp_path, monkeypatch):
    root = tmp_path / "source"
    archive = tmp_path / "archive"
    cases, bindings = fixtures(root)
    (archive / "m6").mkdir(parents=True)
    trials = root / ".runtime/reliability/trials"
    trials.rename(archive / "m6/trials")
    trials.mkdir()
    monkeypatch.setattr(paths, "ROOT", root.resolve())
    monkeypatch.setattr(paths, "archive_root", lambda: archive)
    monkeypatch.setattr(lineage, "ROOT", root.resolve())
    monkeypatch.setattr(lineage, "archive_root", lambda: archive)
    assert len(verify(cases, bindings, root=root)["cases"]) == 6
