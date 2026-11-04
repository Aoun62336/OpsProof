"""Validation tests requiring no database or Redis service."""

import pytest
from pydantic import ValidationError

from opsproof_demo.contracts import CreateJob


def test_minimum_job_duration() -> None:
    assert CreateJob(duration_ms=50).duration_ms == 50


def test_maximum_job_duration() -> None:
    assert CreateJob(duration_ms=2000).duration_ms == 2000


@pytest.mark.parametrize(
    "duration",
    [0, 49, 2001, -1],
)
def test_out_of_range_duration(duration: int) -> None:
    with pytest.raises(ValidationError):
        CreateJob(duration_ms=duration)


def test_reject_implicit_type_conversion() -> None:
    with pytest.raises(ValidationError):
        CreateJob(duration_ms="100")  # type: ignore[arg-type]


def test_reject_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        CreateJob(
            duration_ms=100,
            privileged=True,
        )  # type: ignore[call-arg]
