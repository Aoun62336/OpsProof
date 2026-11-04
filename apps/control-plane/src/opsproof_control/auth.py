"""Local operator authentication and revocable browser sessions."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, SecretStr

from .config import settings
from .db import pool

COOKIE_NAME = "opsproof_session"
SESSION_HOURS = 8

api_key_header = APIKeyHeader(
    name="X-OpsProof-Key",
    auto_error=False,
)

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Operator session"],
)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    access_key: SecretStr


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _key_fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _csrf_token_for(session_token: str) -> str:
    return hmac.new(
        session_token.encode(),
        b"csrf",
        hashlib.sha256,
    ).hexdigest()


def authorize(
    request: Request,
    key: str | None = Depends(api_key_header),
) -> None:
    """Accept either a valid API key or a valid browser session cookie."""
    s = settings()

    # API-key path (used by existing scripts and CI)
    if key is not None:
        if s.api_key and secrets.compare_digest(key, s.api_key):
            return
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )

    # Cookie-session path (used by the React browser interface)
    session_token = request.cookies.get(COOKIE_NAME)
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )

    token_hash = _hash_token(session_token)
    now = datetime.now(UTC)

    with pool().connection() as conn:
        row = conn.execute(
            """
            SELECT token_hash, key_fingerprint, expires_at, revoked_at
            FROM operator_sessions
            WHERE token_hash = %s
            """,
            (token_hash,),
        ).fetchone()

    if row is None or row["revoked_at"] is not None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )

    if row["expires_at"] < now:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )

    # Validate that the stored key fingerprint still matches the current key
    expected_fp = _key_fingerprint(s.api_key)
    if not hmac.compare_digest(row["key_fingerprint"], expected_fp):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )

    # CSRF check for state-changing methods
    if request.method not in ("GET", "HEAD"):
        csrf = request.headers.get("X-OpsProof-CSRF", "")
        expected_csrf = _csrf_token_for(session_token)
        if not hmac.compare_digest(csrf, expected_csrf):
            raise HTTPException(
                status_code=403,
                detail="CSRF token missing or invalid",
            )


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
) -> dict:
    s = settings()

    if not s.api_key or not secrets.compare_digest(
        payload.access_key.get_secret_value(),
        s.api_key,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid access key",
        )

    session_token = secrets.token_hex(32)
    token_hash = _hash_token(session_token)
    key_fp = _key_fingerprint(s.api_key)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=SESSION_HOURS)

    with pool().connection() as conn:
        conn.execute(
            """
            INSERT INTO operator_sessions
                (token_hash, key_fingerprint, created_at, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (token_hash, key_fp, now, expires_at),
        )

    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="strict",
        secure=s.secure_cookies,
        max_age=SESSION_HOURS * 3600,
        path="/",
    )

    csrf_token = _csrf_token_for(session_token)
    return {"authenticated": True, "csrf_token": csrf_token}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
) -> dict:
    session_token = request.cookies.get(COOKIE_NAME)

    if session_token:
        token_hash = _hash_token(session_token)
        with pool().connection() as conn:
            conn.execute(
                """
                UPDATE operator_sessions
                SET revoked_at = now()
                WHERE token_hash = %s
                """,
                (token_hash,),
            )

    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"authenticated": False, "csrf_token": ""}


@router.get("/session")
def session(request: Request) -> dict:
    session_token = request.cookies.get(COOKIE_NAME)
    if not session_token:
        raise HTTPException(status_code=401, detail="No active session")

    token_hash = _hash_token(session_token)
    now = datetime.now(UTC)
    s = settings()

    with pool().connection() as conn:
        row = conn.execute(
            """
            SELECT token_hash, key_fingerprint, expires_at, revoked_at
            FROM operator_sessions
            WHERE token_hash = %s
            """,
            (token_hash,),
        ).fetchone()

    if (
        row is None
        or row["revoked_at"] is not None
        or row["expires_at"] < now
        or not hmac.compare_digest(
            row["key_fingerprint"],
            _key_fingerprint(s.api_key),
        )
    ):
        raise HTTPException(status_code=401, detail="No active session")

    csrf_token = _csrf_token_for(session_token)
    return {"authenticated": True, "csrf_token": csrf_token}
