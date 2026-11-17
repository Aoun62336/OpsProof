"""Workflow syntax checks alone cannot catch missing inputs or skipped test forms."""

from scripts.cloud.check_workflow_contracts import check


def workflow(root, command):
    folder = root / ".github/workflows"
    folder.mkdir(parents=True)
    (folder / "fixture.yml").write_text("steps:\n  - run: " + command + "\n", encoding="utf-8")


def test_missing_checked_in_json_is_rejected(tmp_path):
    workflow(tmp_path, "python -m json.tool docs/cloud/missing.json")
    assert any("missing/unsafe source input" in issue for issue in check(tmp_path))


def test_cloud_function_tests_cannot_be_replaced_with_unittest_discovery(tmp_path):
    workflow(tmp_path, "python -m unittest discover -s scripts/cloud/tests -v")
    assert any("require pytest discovery" in issue for issue in check(tmp_path))


def test_real_inputs_and_pytest_are_accepted_without_generated_artifacts(tmp_path):
    (tmp_path / "docs/cloud").mkdir(parents=True)
    (tmp_path / "docs/cloud/cost-input.example.json").write_text("{}", encoding="utf-8")
    workflow(
        tmp_path,
        "python -m json.tool docs/cloud/cost-input.example.json && "
        "python -m pytest scripts/cloud/tests -q > .runtime/result.json",
    )
    assert check(tmp_path) == []
