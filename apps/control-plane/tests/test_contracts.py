"""Control-plane request and state validation tests."""

import pytest
from pydantic import ValidationError

from opsproof_control.contracts import CreateRun, RunStatus


def test_valid_experiment() -> None:
    run = CreateRun(
        scenario="queue-burst",
        count=5,
        duration_ms=250,
    )

    assert run.count == 5
    assert run.duration_ms == 250


@pytest.mark.parametrize(
    "count",
    [0, -1, 9, 100],
)
def test_invalid_job_count(count: int) -> None:
    with pytest.raises(ValidationError):
        CreateRun(
            scenario="queue-burst",
            count=count,
            duration_ms=250,
        )


@pytest.mark.parametrize(
    "duration",
    [0, 49, 751, 5000],
)
def test_invalid_job_duration(duration: int) -> None:
    with pytest.raises(ValidationError):
        CreateRun(
            scenario="queue-burst",
            count=3,
            duration_ms=duration,
        )


def test_arbitrary_scenario_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateRun(
            scenario="delete-database",  # type: ignore[arg-type]
            count=3,
            duration_ms=250,
        )


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateRun.model_validate(
            {
                "scenario": "queue-burst",
                "count": 3,
                "duration_ms": 250,
                "shell_command": "not-allowed",
            }
        )


def test_state_contract_is_explicit() -> None:
    assert {status.value for status in RunStatus} == {
        "queued",
        "running",
        "verifying",
        "succeeded",
        "failed",
    }
