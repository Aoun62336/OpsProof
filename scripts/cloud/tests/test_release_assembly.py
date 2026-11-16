"""Prevent release manifests that mix image roles, source commits or workflow runs."""

from copy import deepcopy

import pytest

from scripts.cloud.assemble_release_manifest import assemble
from scripts.cloud.verify_release_manifest import NAMES


def receipts():
    return [
        {
            "role": name,
            "source_sha": "a" * 40,
            "repository": "example/opsproof",
            "workflow_run_id": 123,
            "digest": "sha256:" + str(i) * 64,
        }
        for i, name in enumerate(NAMES)
    ]


def build(rows):
    return assemble(rows, source_sha="a" * 40, repository="example/opsproof", run_id=123)


def test_four_images_from_one_run():
    assert set(build(receipts())["images"]) == set(NAMES)


@pytest.mark.parametrize(
    "field,value",
    [
        ("workflow_run_id", 456),
        ("source_sha", "b" * 40),
        ("repository", "other/opsproof"),
        ("role", "web"),
    ],
)
def test_mixed_or_duplicate_receipts_fail(field, value):
    rows = deepcopy(receipts())
    rows[0][field] = value
    with pytest.raises(ValueError):
        build(rows)


def test_partial_release_is_not_ready():
    with pytest.raises(ValueError):
        build(receipts()[:-1])
