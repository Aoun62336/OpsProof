"""PostgreSQL-backed trial ledger. All state changes use row locks and audit events.

NOTE: This module never performs a fault or calls Kubernetes. API callers cannot
assert injection, independent verification, or cleanup by supplying JSON flags.
"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from .trial_catalog import Scenario, fixed_target
from .trial_state import TrialPhase, TrialRecord, transition

ACTIVE = frozenset(
    {
        TrialPhase.REQUESTED,
        TrialPhase.PREFLIGHT,
        TrialPhase.ARMED,
        TrialPhase.INJECTED,
        TrialPhase.OBSERVING,
        TrialPhase.RECOVERING,
        TrialPhase.VERIFYING,
    }
)


class TrialConflict(Exception):
    """A state, idempotency or target ownership conflict."""


class TrialNotFound(Exception):
    """The requested trial does not exist."""


def _audit(conn: Connection, trial_id: UUID, kind: str, details: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO m6_trial_events (trial_id,kind,details) VALUES (%s,%s,%s)",
        (trial_id, kind, Jsonb(details or {})),
    )


def _db_now(conn: Connection) -> datetime:
    # clock_timestamp() advances while waiting for a row lock; transaction now()
    # could authorize a request whose approval expired while it was blocked.
    return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]


def _locked(conn: Connection, trial_id: UUID) -> dict:
    row = conn.execute("SELECT * FROM m6_trials WHERE id=%s FOR UPDATE", (trial_id,)).fetchone()
    if row is None:
        raise TrialNotFound
    return row


def _record(row: dict) -> TrialRecord:
    return TrialRecord(
        id=row["id"],
        scenario=row["scenario"],
        phase=TrialPhase(row["phase"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        target=row["target"],
        approved_test_scope=row["approved_test_scope"],
        cleanup_plan_confirmed=row["cleanup_plan_confirmed"],
        injection_acknowledged=row["injection_acknowledged"],
        independent_verified=row["independent_verified"],
        cleanup_verified=row["cleanup_verified"],
    )


def _move(
    conn: Connection,
    row: dict,
    next_phase: TrialPhase,
    *,
    evidence: dict[str, bool] | None = None,
    error: str | None = None,
) -> dict:
    if next_phase in (TrialPhase.ABORTED, TrialPhase.FAILED) and row.get("dispatch_intent_at"):
        if not (evidence or {}).get("cleanup_verified", row["cleanup_verified"]):
            raise TrialConflict("Possibly dispatched trials require independently verified cleanup")
    updated = transition(_record(row), next_phase, observed_at=_db_now(conn), **(evidence or {}))
    complete = next_phase not in ACTIVE
    # API/coordinator roles cannot write verifier/actuator columns. Touch those
    # columns only for trusted execution transitions that actually supply them.
    if {"injection_acknowledged", "independent_verified", "cleanup_verified"} & set(evidence or {}):
        conn.execute(
            "UPDATE m6_trials SET injection_acknowledged=%s,independent_verified=%s,"
            "cleanup_verified=%s WHERE id=%s",
            (
                updated.injection_acknowledged,
                updated.independent_verified,
                updated.cleanup_verified,
                row["id"],
            ),
        )
    result = conn.execute(
        """UPDATE m6_trials SET phase=%s,updated_at=%s,
             approved_test_scope=%s,cleanup_plan_confirmed=%s,
             completed_at=CASE WHEN %s THEN now() ELSE completed_at END,
             error=COALESCE(%s,error)
           WHERE id=%s RETURNING *""",
        (
            next_phase.value,
            updated.updated_at,
            updated.approved_test_scope,
            updated.cleanup_plan_confirmed,
            complete,
            error[:300] if error else None,
            row["id"],
        ),
    ).fetchone()
    _audit(conn, row["id"], f"phase:{next_phase.value}", {"from": row["phase"]})
    return result


def create_trial(
    conn: Connection, *, request_key: str, scenario: Scenario, source_revision: str
) -> tuple[dict, bool]:
    """Idempotency and one-active-trial-per-target are DB-enforced."""
    payload = {"scenario": scenario.value, "source_revision": source_revision}
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    target = fixed_target(scenario)
    if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", request_key):
        raise ValueError("Invalid idempotency key")
    if not re.fullmatch(r"[a-f0-9]{7,64}", source_revision):
        raise ValueError("Invalid source revision")
    # Serialize creation against retained reservations as well as active rows.
    # This closes the check-then-insert race with indeterminate terminal trials.
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (target,))
    # An existing key must resolve identically even if another active trial exists.
    existing = conn.execute(
        "SELECT * FROM m6_trials WHERE request_key=%s", (request_key,)
    ).fetchone()
    if existing:
        if existing["request_hash"] != fingerprint:
            raise TrialConflict("Idempotency key reused with different payload")
        return existing, False
    if (
        conn.execute("SELECT trial_id FROM m6_target_leases WHERE target=%s", (target,)).fetchone()
        is not None
    ):
        raise TrialConflict("Target has a retained safety reservation")
    try:
        with conn.transaction():
            row = conn.execute(
                """INSERT INTO m6_trials
                   (id,request_key,request_hash,scenario,target,source_revision)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (uuid4(), request_key, fingerprint, scenario.value, target, source_revision),
            ).fetchone()
            _audit(conn, row["id"], "requested", {"scenario": scenario.value})
            conn.execute(
                "INSERT INTO m6_trial_outbox (trial_id,event_type) "
                "VALUES (%s,'preflight_requested')",
                (row["id"],),
            )
            return row, True
    except UniqueViolation as exc:
        # Includes duplicate idempotency under a concurrent insert or target collision.
        existing = conn.execute(
            "SELECT * FROM m6_trials WHERE request_key=%s", (request_key,)
        ).fetchone()
        if existing is not None and existing["request_hash"] == fingerprint:
            return existing, False
        raise TrialConflict("Target already has an active trial or key conflicts") from exc


def get_trial(conn: Connection, trial_id: UUID) -> dict:
    row = conn.execute("SELECT * FROM m6_trials WHERE id=%s", (trial_id,)).fetchone()
    if row is None:
        raise TrialNotFound
    return row


def list_trials(conn: Connection, *, limit: int = 30) -> list[dict]:
    return conn.execute(
        "SELECT * FROM m6_trials ORDER BY created_at DESC LIMIT %s", (limit,)
    ).fetchall()


def events(conn: Connection, trial_id: UUID) -> list[dict]:
    get_trial(conn, trial_id)
    return conn.execute(
        "SELECT * FROM m6_trial_events WHERE trial_id=%s ORDER BY id LIMIT 500", (trial_id,)
    ).fetchall()


def claim_preflight(conn: Connection) -> UUID | None:
    """Idempotent claim for a non-mutating worker. No Kubernetes API access."""
    row = conn.execute(
        """SELECT * FROM m6_trials WHERE phase='requested'
           ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"""
    ).fetchone()
    if row is None:
        return None
    _move(conn, row, TrialPhase.PREFLIGHT)
    conn.execute(
        "UPDATE m6_trial_outbox SET dispatched_at=now() "
        "WHERE trial_id=%s AND event_type='preflight_requested' AND dispatched_at IS NULL",
        (row["id"],),
    )
    _audit(
        conn, row["id"], "preflight:source_contract_only", {"not_a_live_cluster_preflight": True}
    )
    return row["id"]


def arm_trial(
    conn: Connection,
    trial_id: UUID,
    *,
    approved_scope: bool,
    cleanup_confirmed: bool,
    confirmation: str,
) -> dict:
    if (
        confirmation != "ARM M6 LOCAL TRIAL"
        or approved_scope is not True
        or cleanup_confirmed is not True
    ):
        raise TrialConflict("Explicit test scope and cleanup confirmation required")
    with conn.transaction():
        return _arm_locked(conn, trial_id)


def _arm_locked(conn: Connection, trial_id: UUID) -> dict:
    row = _locked(conn, trial_id)
    if row["phase"] != TrialPhase.PREFLIGHT:
        raise TrialConflict("Trial not in preflight")
    scope = conn.execute(
        "INSERT INTO m6_execution_leases(scope,trial_id) VALUES ('k3d-opsproof',%s) "
        "ON CONFLICT DO NOTHING RETURNING trial_id",
        (trial_id,),
    ).fetchone()
    if scope is None:
        raise TrialConflict("Another trial reserves the shared local environment")
    # Source-only preflight is insufficient to execute a live fault.
    # Approval becomes a short-lived intent; execution is not wired to this API.
    _move(
        conn,
        row,
        TrialPhase.ARMED,
        evidence={
            "approved_test_scope": True,
            "cleanup_plan_confirmed": True,
        },
    )
    lease = conn.execute(
        """INSERT INTO m6_target_leases (target,trial_id,fence_token)
           VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING fence_token""",
        (row["target"], trial_id, uuid4()),
    ).fetchone()
    if lease is None:
        raise TrialConflict("Target is reserved by another trial")
    approved_now = _db_now(conn)
    updated = conn.execute(
        """UPDATE m6_trials SET approved_at=%s, approval_expires_at=%s
           WHERE id=%s RETURNING *""",
        (approved_now, approved_now + timedelta(seconds=120), trial_id),
    ).fetchone()
    _audit(conn, trial_id, "operator_armed_intent", {"expires_in_seconds": 120})
    return updated


def request_abort(conn: Connection, trial_id: UUID) -> dict:
    row = _locked(conn, trial_id)
    if TrialPhase(row["phase"]) not in ACTIVE:
        raise TrialConflict("Terminal trial cannot be aborted again")
    if row.get("dispatch_intent_at") and row["phase"] == "armed":
        _audit(conn, trial_id, "abort_requested_after_dispatch_intent")
        return _move(
            conn,
            row,
            TrialPhase.INDETERMINATE,
            error="Abort after dispatch intent; target retained pending cleanup",
        )
    if row["phase"] in ("requested", "preflight", "armed") and not row["injection_acknowledged"]:
        updated = _move(conn, row, TrialPhase.ABORTED)
        _audit(conn, trial_id, "operator_aborted_before_dispatch")
        conn.execute("DELETE FROM m6_target_leases WHERE trial_id=%s", (trial_id,))
        conn.execute("DELETE FROM m6_execution_leases WHERE trial_id=%s", (trial_id,))
        return updated
    updated = conn.execute(
        "UPDATE m6_trials SET abort_requested=true,updated_at=now() WHERE id=%s RETURNING *",
        (trial_id,),
    ).fetchone()
    _audit(conn, trial_id, "abort_requested_injection_uncertain")
    conn.execute(
        "INSERT INTO m6_trial_outbox (trial_id,event_type) VALUES (%s,'abort_requested')",
        (trial_id,),
    )
    return updated


def expire_uninjected_approvals(conn: Connection) -> int:
    """Expiry cannot release injected or uncertain targets."""
    rows = conn.execute(
        """SELECT * FROM m6_trials WHERE phase='armed'
           AND injection_acknowledged=false AND dispatch_intent_at IS NULL
           AND approval_expires_at<=clock_timestamp()
           ORDER BY approved_at FOR UPDATE SKIP LOCKED LIMIT 20"""
    ).fetchall()
    for row in rows:
        _move(conn, row, TrialPhase.ABORTED, error="Local approval expired without injection")
        conn.execute("DELETE FROM m6_target_leases WHERE trial_id=%s", (row["id"],))
        conn.execute("DELETE FROM m6_execution_leases WHERE trial_id=%s", (row["id"],))
        _audit(conn, row["id"], "approval_expired_without_injection")
    return len(rows)


def begin_dispatch(
    conn: Connection,
    trial_id: UUID,
    *,
    fence_token: UUID,
    target_uid: str,
    target_version: str,
    maximum_seconds: int,
) -> UUID:
    """Commit this intent BEFORE any external mutation. Never retry an intent.

    Only a restricted local executor may call this after real preflight. The
    caller must exit its transaction before sending. A crash on either side of
    the send boundary is conservatively indeterminate, not permission to replay.
    """
    _assert_fence(conn, trial_id, fence_token)
    row = _locked(conn, trial_id)
    now = _db_now(conn)
    if (
        row["phase"] != "armed"
        or row.get("dispatch_intent_at")
        or row.get("abort_requested")
        or not row["approval_expires_at"]
        or row["approval_expires_at"] <= now
    ):
        raise TrialConflict("Dispatch requires fresh, unused, unaborted approval")
    if (
        type(maximum_seconds) is not int
        or not 1 <= maximum_seconds <= 600
        or not isinstance(target_uid, str)
        or not 1 <= len(target_uid) <= 128
        or not isinstance(target_version, str)
        or not 1 <= len(target_version) <= 128
    ):
        raise ValueError("Bounded execution and exact observed target identity required")
    dispatch_id = uuid4()
    conn.execute(
        "UPDATE m6_trials SET dispatch_id=%s,dispatch_intent_at=%s,dispatch_deadline=%s,"
        "target_uid=%s,target_version=%s,updated_at=%s WHERE id=%s",
        (
            dispatch_id,
            now,
            now + timedelta(seconds=maximum_seconds),
            target_uid,
            target_version,
            now,
            trial_id,
        ),
    )
    _audit(
        conn,
        trial_id,
        "dispatch_intent",
        {
            "dispatch_id": str(dispatch_id),
            "target_uid": target_uid,
            "target_version": target_version,
            "maximum_seconds": maximum_seconds,
        },
    )
    return dispatch_id


def expire_dispatched_trials(conn: Connection) -> int:
    rows = conn.execute(
        "SELECT * FROM m6_trials WHERE phase IN "
        "('armed','injected','observing','recovering','verifying') "
        "AND dispatch_deadline<=clock_timestamp() ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 20"
    ).fetchall()
    for row in rows:
        _move(
            conn,
            row,
            TrialPhase.INDETERMINATE,
            error="Execution/verification deadline exceeded; target remains reserved",
        )
        _audit(conn, row["id"], "execution_deadline_exceeded")
    return len(rows)


def verified_complete(
    conn: Connection,
    trial_id: UUID,
    *,
    fence_token: UUID,
    independently_verified: bool,
    cleanup_verified: bool,
) -> dict:
    """Restricted service-level helper, NOT exposed by operator HTTP routes.

    A separate verifier supplies a dispatch-bound receipt and actual postconditions.
    """
    _assert_fence(conn, trial_id, fence_token)
    row = _locked(conn, trial_id)
    if row["phase"] != TrialPhase.VERIFYING:
        raise TrialConflict("Completion requires verifying phase")
    if independently_verified is not True or cleanup_verified is not True:
        raise TrialConflict("Independent postconditions and cleanup required")
    if row["abort_requested"]:
        raise TrialConflict("Aborted execution cannot be reported as success")
    if row["dispatch_deadline"] <= _db_now(conn):
        raise TrialConflict("Verification deadline expired")
    verification = _require_verification(conn, row)
    if verification["hypothesis_verified"] is not True:
        raise TrialConflict("Independent evidence did not establish the hypothesis")
    rows = conn.execute(
        "SELECT kind FROM m6_trial_artifacts WHERE trial_id=%s "
        "AND kind IN ('injection','independent','cleanup')",
        (trial_id,),
    ).fetchall()
    if {r["kind"] for r in rows} != {"injection", "independent", "cleanup"}:
        raise TrialConflict("Three independently recorded artifact classes required")
    updated = _move(
        conn,
        row,
        TrialPhase.SUCCEEDED,
        evidence={
            "independent_verified": True,
            "cleanup_verified": True,
        },
    )
    conn.execute("DELETE FROM m6_target_leases WHERE trial_id=%s", (trial_id,))
    conn.execute("DELETE FROM m6_execution_leases WHERE trial_id=%s", (trial_id,))
    return updated


def _assert_fence(conn: Connection, trial_id: UUID, token: UUID) -> None:
    # Lock order is always trial -> target lease. Abort/expiry paths use the
    # same order; reversing it can cause a PostgreSQL deadlock under contention.
    _locked(conn, trial_id)
    row = conn.execute(
        "SELECT fence_token FROM m6_target_leases WHERE trial_id=%s FOR UPDATE", (trial_id,)
    ).fetchone()
    if row is None or row["fence_token"] != token:
        raise TrialConflict("Missing or stale M6 target fence token")


def record_verification(
    conn: Connection,
    trial_id: UUID,
    *,
    fence_token: UUID,
    report_json: str,
    relative_path: str,
    sha256: str,
) -> None:
    """Service-only insertion of the independently produced immutable receipt.

    The caller validates file bytes/hash and the observer process result first.
    No operator API accepts receipt fields or verifier success assertions.
    """
    from .trial_verification import VerificationReceipt

    proof = VerificationReceipt.model_validate_json(report_json)
    _assert_fence(conn, trial_id, fence_token)
    row = _locked(conn, trial_id)
    now = _db_now(conn)
    if (
        proof.trial_id != trial_id
        or proof.dispatch_id != row.get("dispatch_id")
        or proof.target_uid != row.get("target_uid")
        or not row.get("dispatch_intent_at")
        or proof.verified_at < row["dispatch_intent_at"]
        or proof.verified_at > now + timedelta(seconds=5)
        or proof.cleanup_verified is not True
        or not proof.checks
        or not all(proof.checks.values())
    ):
        raise TrialConflict("Verification identity, time or cleanup checks do not match dispatch")
    attach_artifact(
        conn,
        trial_id,
        fence_token=fence_token,
        kind="independent",
        relative_path=relative_path,
        sha256=sha256,
    )
    conn.execute(
        "INSERT INTO m6_trial_verifications "
        "(trial_id,dispatch_id,observer_id,target_uid,report_sha256,observer_sha256,"
        "verified_at,cleanup_verified,hypothesis_verified,report) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            trial_id,
            proof.dispatch_id,
            proof.observer_id,
            proof.target_uid,
            sha256,
            proof.observer_sha256,
            proof.verified_at,
            proof.cleanup_verified,
            proof.hypothesis_verified,
            Jsonb(proof.model_dump(mode="json")),
        ),
    )
    _audit(
        conn,
        trial_id,
        "independent_verification_recorded",
        {
            "dispatch_id": str(proof.dispatch_id),
            "report_sha256": sha256,
            "hypothesis_verified": proof.hypothesis_verified,
        },
    )


def _require_verification(conn: Connection, row: dict) -> dict:
    proof = conn.execute(
        "SELECT * FROM m6_trial_verifications WHERE trial_id=%s "
        "ORDER BY verified_at DESC,id DESC LIMIT 1",
        (row["id"],),
    ).fetchone()
    if (
        not proof
        or proof["dispatch_id"] != row["dispatch_id"]
        or proof["target_uid"] != row["target_uid"]
        or not proof["cleanup_verified"]
    ):
        raise TrialConflict("Independent dispatch-bound cleanup receipt required")
    return proof


def attach_artifact(
    conn: Connection,
    trial_id: UUID,
    *,
    fence_token: UUID,
    kind: str,
    relative_path: str,
    sha256: str,
    observations: dict | None = None,
) -> None:
    """Trusted-worker-only evidence identity; never exposed to an operator API.

    Hash and relative-path checks are necessary but not sufficient to prove truth.
    """
    _assert_fence(conn, trial_id, fence_token)
    row = _locked(conn, trial_id)
    if row["phase"] in ("succeeded", "failed", "aborted"):
        raise TrialConflict("Terminal evidence cannot be changed")
    if kind not in ("preflight", "injection", "independent", "cleanup", "metric", "log", "trace"):
        raise ValueError("Unsupported evidence category")
    if not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise ValueError("Invalid SHA-256 digest")
    summary = observations or {}
    if not isinstance(summary, dict) or len(json.dumps(summary, allow_nan=False).encode()) > 60_000:
        raise ValueError("Observed data must be a bounded JSON object")
    path_parts = relative_path.replace("\\", "/").split("/")
    if (
        len(relative_path) > 240
        or not relative_path.startswith((".runtime/m6/", ".runtime/reliability/"))
        or any(part in ("", ".", "..") for part in path_parts)
        or ":" in relative_path
        or "\\" in relative_path
    ):
        raise ValueError("Only canonical relative trial evidence paths are allowed")
    conn.execute(
        """INSERT INTO m6_trial_artifacts (trial_id,kind,relative_path,sha256,observations)
           VALUES (%s,%s,%s,%s,%s)""",
        (trial_id, kind, relative_path, sha256, Jsonb(summary)),
    )
    _audit(conn, trial_id, "artifact_added", {"kind": kind, "sha256": sha256})


def acknowledge_injection(
    conn: Connection,
    trial_id: UUID,
    *,
    fence_token: UUID,
    dispatch_id: UUID,
    receipt_path: str,
    receipt_sha256: str,
) -> dict:
    """Use ONLY from a future restricted actuator with a genuine action receipt.

    This helper never performs injection and is intentionally not an HTTP route.
    """
    _assert_fence(conn, trial_id, fence_token)
    row = _locked(conn, trial_id)
    if (
        row["phase"] != TrialPhase.ARMED
        or not row["approved_test_scope"]
        or not row["dispatch_intent_at"]
        or row["dispatch_id"] != dispatch_id
        or row["abort_requested"]
    ):
        raise TrialConflict("Unarmed M6 trial")
    if row["dispatch_deadline"] <= _db_now(conn):
        raise TrialConflict("Action receipt arrived after execution deadline")
    attach_artifact(
        conn,
        trial_id,
        fence_token=fence_token,
        kind="injection",
        relative_path=receipt_path,
        sha256=receipt_sha256,
    )
    return _move(conn, row, TrialPhase.INJECTED, evidence={"injection_acknowledged": True})


def progress(
    conn: Connection, trial_id: UUID, *, fence_token: UUID, next_phase: TrialPhase
) -> dict:
    """Only a restricted worker holding the exact fence may advance a live run."""
    _assert_fence(conn, trial_id, fence_token)
    row = _locked(conn, trial_id)
    if next_phase not in (TrialPhase.OBSERVING, TrialPhase.RECOVERING, TrialPhase.VERIFYING):
        raise TrialConflict("Unsupported worker-only transition")
    return _move(conn, row, next_phase)


def verified_failure(
    conn: Connection, trial_id: UUID, *, fence_token: UUID, cleanup_verified: bool, reason: str
) -> dict:
    """Preserve a failed hypothesis while releasing only independently clean targets."""
    _assert_fence(conn, trial_id, fence_token)
    row = _locked(conn, trial_id)
    if row["phase"] != "verifying" or cleanup_verified is not True:
        raise TrialConflict("Failed execution still requires verifying phase and cleanup")
    _require_verification(conn, row)
    kinds = conn.execute("SELECT kind FROM m6_trial_artifacts WHERE trial_id=%s", (trial_id,))
    if "cleanup" not in {item["kind"] for item in kinds.fetchall()}:
        raise TrialConflict("Independent cleanup artifact required")
    result = _move(conn, row, TrialPhase.FAILED, evidence={"cleanup_verified": True}, error=reason)
    conn.execute("DELETE FROM m6_target_leases WHERE trial_id=%s", (trial_id,))
    conn.execute("DELETE FROM m6_execution_leases WHERE trial_id=%s", (trial_id,))
    return result


def mark_uncertain(conn: Connection, trial_id: UUID, *, fence_token: UUID, reason: str) -> dict:
    """Do not auto-release target when an actuator result or cleanup is unknown."""
    _assert_fence(conn, trial_id, fence_token)
    row = _locked(conn, trial_id)
    if row["phase"] not in ("armed", "injected", "observing", "recovering", "verifying"):
        raise TrialConflict("Uncertainty requires an in-flight injection")
    if row["phase"] == "armed" and not row.get("dispatch_intent_at"):
        raise TrialConflict("No dispatch intent to reconcile")
    return _move(conn, row, TrialPhase.INDETERMINATE, error=reason[:300])


def resolve_uncertain(conn: Connection, trial_id: UUID, *, fence_token: UUID, reason: str) -> None:
    """Separate reconciliation keeps the original terminal outcome immutable.

    Service-only: independent and cleanup artifacts must be collected and checked
    by the verifier before this is invoked. No operator HTTP success endpoint.
    """
    _assert_fence(conn, trial_id, fence_token)
    row = _locked(conn, trial_id)
    if row["phase"] != "indeterminate" or not 10 <= len(reason) <= 300:
        raise TrialConflict("An uncertain trial and an explicit reconciliation reason required")
    _require_verification(conn, row)
    kinds = conn.execute(
        "SELECT kind FROM m6_trial_artifacts WHERE trial_id=%s", (trial_id,)
    ).fetchall()
    if not {"independent", "cleanup"}.issubset({item["kind"] for item in kinds}):
        raise TrialConflict("Independent restoration and cleanup evidence required")
    conn.execute(
        "INSERT INTO m6_trial_resolutions(trial_id,reason) VALUES (%s,%s)", (trial_id, reason)
    )
    _audit(conn, trial_id, "uncertainty_reconciled_target_released", {"reason": reason})
    conn.execute("DELETE FROM m6_target_leases WHERE trial_id=%s", (trial_id,))
    conn.execute("DELETE FROM m6_execution_leases WHERE trial_id=%s", (trial_id,))
