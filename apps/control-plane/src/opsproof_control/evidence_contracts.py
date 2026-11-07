"""Pure fail-closed contracts for exact demo-job evidence."""

from uuid import UUID

VALID_JOB_STATES = frozenset(("queued", "processing", "completed", "failed"))


def required_job_ids(details: object, expected_count: int) -> list[str]:
    """Require one unique, canonical UUID per job requested by the experiment."""
    if type(expected_count) is not int or not 1 <= expected_count <= 8:
        raise ValueError("Invalid experiment job count")
    if not isinstance(details, dict):
        raise ValueError("Missing job event details")
    values = details.get("job_ids")
    if not isinstance(values, list) or len(values) != expected_count:
        raise ValueError("Job IDs do not match the experiment count")
    if "submitted" in details and (
        type(details["submitted"]) is not int or details["submitted"] != expected_count
    ):
        raise ValueError("Submitted count disagrees with the experiment")
    result: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raise ValueError("Job identifier must be a string UUID")
        try:
            canonical = str(UUID(raw))
        except ValueError as exc:
            raise ValueError("Invalid job identifier") from exc
        if canonical != raw:
            raise ValueError("Noncanonical job identifier")
        result.append(canonical)
    if len(set(result)) != len(result):
        raise ValueError("Duplicate linked job identifier")
    return result


def exact_job_status(payload: object, expected_id: str) -> str:
    """A status is evidence only if it belongs to the exact linked job."""
    if not isinstance(payload, dict) or payload.get("id") != expected_id:
        raise ValueError("Job response identity mismatch")
    state = payload.get("status")
    if not isinstance(state, str) or state not in VALID_JOB_STATES:
        raise ValueError("Unknown job status")
    return state
