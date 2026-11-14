import json
from pathlib import Path

import pytest

from scripts.m6.qualify import benchmark

DATASET = Path(__file__).parents[3] / "benchmarks/ai/qualification_v1.json"


def test_frozen_synthetic_labels_do_not_require_network():
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    report = benchmark(data)
    assert report["case_count"] == 20
    assert report["hypothesis_correct"] == 20
    assert report["abstention_correct"] == 20
    assert report["invalid_or_error"] == 0
    assert all(row["prediction"]["action"] == "none" for row in report["cases"])


def test_corrupt_dataset_fails_closed():
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    data["cases"].pop()
    with pytest.raises(ValueError):
        benchmark(data)
