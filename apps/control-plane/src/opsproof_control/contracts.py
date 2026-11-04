"""Versioned API contracts for OpsProof experiments."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CreateRun(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    scenario: Literal["queue-burst"]
    count: int = Field(ge=1, le=8)
    duration_ms: int = Field(ge=50, le=750)


class RunView(BaseModel):
    id: UUID
    scenario: str
    count: int
    duration_ms: int
    status: RunStatus
    result: dict
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class EventView(BaseModel):
    id: int
    type: str
    details: dict
    created_at: datetime
