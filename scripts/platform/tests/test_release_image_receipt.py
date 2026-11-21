"""Release drills cannot silently inherit an old locally cached application."""

import pytest

from scripts.platform import build_release_images as releases


def test_release_requires_current_source_and_matching_image_identity(monkeypatch):
    digest = "a" * 64
    monkeypatch.setattr(releases, "context_hash", lambda _: digest)
    receipt = {
        "source_content_sha256": digest,
        "tag": "opsproof-demo:src-" + digest[:16],
        "local_image_id": "sha256:" + "b" * 64,
    }
    assert releases.base_image(receipt) == (receipt["tag"], receipt["local_image_id"])
    for field in receipt:
        with pytest.raises(ValueError, match="current demo source"):
            releases.base_image({**receipt, field: "old"})
