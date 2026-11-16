"""Regression cases for real Helm dependency layouts and unsafe tar metadata."""

import io
import tarfile

import pytest

from scripts.cloud import install_controllers as installer


def archive(path, members):
    with tarfile.open(path, "w:gz") as output:
        for name, value in members:
            entry = tarfile.TarInfo(name)
            payload = value.encode()
            entry.size = len(payload)
            output.addfile(entry, io.BytesIO(payload))


def test_root_and_packaged_dependency_are_distinct_identities(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "CHARTS", tmp_path)
    item = {"chart": "argo-cd", "version": "10.17.1"}
    archive(
        tmp_path / "argo-cd-10.17.1.tgz",
        [
            ("argo-cd/Chart.yaml", "apiVersion: v2\nname: argo-cd\nversion: 10.17.1\n"),
            (
                "argo-cd/charts/redis-ha/Chart.yaml",
                "apiVersion: v2\nname: redis-ha\nversion: 4.0.0\n",
            ),
        ],
    )
    assert len(installer.chart_metadata(item)) == 2
    assert len(installer.chart_sha(item)) == 64


@pytest.mark.parametrize("member", ["../Chart.yaml", "/argo-cd/Chart.yaml", "other/Chart.yaml"])
def test_unsafe_tar_members_fail_closed(tmp_path, monkeypatch, member):
    monkeypatch.setattr(installer, "CHARTS", tmp_path)
    item = {"chart": "argo-cd", "version": "10.17.1"}
    archive(tmp_path / "argo-cd-10.17.1.tgz", [(member, "name: argo-cd\nversion: 10.17.1\n")])
    with pytest.raises(ValueError, match="Unsafe"):
        installer.chart_sha(item)


def test_wrong_root_version_is_not_hidden_by_dependency(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "CHARTS", tmp_path)
    item = {"chart": "argo-cd", "version": "10.17.1"}
    archive(
        tmp_path / "argo-cd-10.17.1.tgz",
        [
            ("argo-cd/Chart.yaml", "apiVersion: v2\nname: argo-cd\nversion: 10.0.0\n"),
            (
                "argo-cd/charts/other/Chart.yaml",
                "apiVersion: v2\nname: argo-cd\nversion: 10.17.1\n",
            ),
        ],
    )
    with pytest.raises(ValueError, match="root identity"):
        installer.chart_sha(item)
