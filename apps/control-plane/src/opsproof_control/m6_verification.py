"""Strict identity for evidence produced by the separate local verifier.

This receipt binds observations to a dispatch. It is not a cryptographic claim
against the machine/database administrator or a replacement for live evidence.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class VerificationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    trial_id: UUID
    dispatch_id: UUID
    observer_id: UUID
    target_uid: Annotated[str, Field(min_length=1, max_length=128)]
    verified_at: datetime
    observer_sha256: Digest
    cleanup_verified: bool
    hypothesis_verified: bool
    checks: dict[str, bool]

    @field_validator("verified_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timezone-aware verification time required")
        return value

    @field_validator("checks")
    @classmethod
    def required_cleanup_checks(cls, value):
        required = {"current_health", "exact_jobs", "original_configuration", "observer_identity"}
        if not required.issubset(value) or not all(value.values()):
            raise ValueError("All independent cleanup checks are required and must pass")
        return value
