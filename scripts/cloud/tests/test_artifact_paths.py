"""Archive lookup preserves immutable locators without allowing path escape."""

import pytest

from scripts import paths


@pytest.mark.parametrize("value", [".env", ".runtime/../.env", ".runtime//file", "C:/file"])
def test_invalid_locator_is_rejected(value, tmp_path):
    with pytest.raises(ValueError):
        paths.read_artifact(value, root=tmp_path)


def test_isolated_source_does_not_read_owner_history(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "archive_root", lambda: tmp_path / "archive")
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive/file.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        paths.read_artifact(".runtime/file.json", root=tmp_path / "source")


def test_current_and_archived_locations_preserve_identical_bytes(tmp_path, monkeypatch):
    source = tmp_path / "source"
    archive = tmp_path / "archive"
    (archive / "m6/trials/example").mkdir(parents=True)
    expected = b'{"immutable":true}\r\n'
    old = archive / "m6/trials/example/result.json"
    old.write_bytes(expected)
    monkeypatch.setattr(paths, "ROOT", source.resolve())
    monkeypatch.setattr(paths, "archive_root", lambda: archive)
    found = paths.read_artifact(".runtime/reliability/trials/example/result.json", root=source)
    assert found.read_bytes() == expected
    assert paths.artifact_locator(found) == ".runtime/m6/trials/example/result.json"


def test_tool_root_cannot_be_inside_checkout(monkeypatch):
    monkeypatch.setenv("OPSPROOF_LOCAL_DIR", str(paths.ROOT / ".runtime/tools"))
    with pytest.raises(ValueError, match="outside"):
        paths.local_root()
