"""Versioned HTTP payloads for the demonstration workload."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateJob(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    duration_ms: int = Field(ge=50, le=2000)


class JobDetails(BaseModel):
    id: UUID
    status: JobStatus
    duration_ms: int
    attempts: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class JobCounts(BaseModel):
    queued: int
    processing: int
    completed: int
    failed: int
