import pytest

from scripts.m6.collect_queue_state import parse_group


def test_lag_and_pending_kept_separate():
    row = parse_group([{"name": "opsproof-workers", "lag": 5, "pending": 7, "consumers": 1}])
    assert row["lag"] == 5 and row["pending"] == 7
    assert row["lag_known"] is True


def test_null_lag_is_unknown_not_zero():
    row = parse_group([{"name": "opsproof-workers", "lag": None, "pending": 4}])
    assert row["lag"] is None
    assert not row["lag_known"]


@pytest.mark.parametrize(
    "sample",
    [
        [],
        [{"name": "wrong", "lag": 0, "pending": 0}],
        [{"name": "opsproof-workers", "lag": -1, "pending": 0}],
        [{"name": "opsproof-workers", "lag": 0, "pending": None}],
        [{"name": "opsproof-workers", "lag": True, "pending": 0}],
    ],
)
def test_bad_or_missing_redis_group_rejected(sample):
    with pytest.raises(ValueError):
        parse_group(sample)
