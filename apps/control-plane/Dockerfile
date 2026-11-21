# syntax=docker/dockerfile:1.7

FROM cgr.dev/chainguard/wolfi-base:latest@sha256:be019c1c74fe69204a42c4e10bc4d886a49bf5403ffa74374ef7baa408fc9a26 AS python-base

# Vendor-signed glibc packages preserve the Python minor version and include the
# upstream SQLite fixes; no unstable repository or locally patched library.
RUN apk upgrade --no-cache \
    && apk add --no-cache \
        python-3.14=3.14.10_git20261118-r0 \
        sqlite-libs=3.54.1-r1 \
        tzdata

FROM python-base AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 \
    /uv /uvx /bin/

ENV UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.14 \
    UV_CONCURRENT_DOWNLOADS=2 \
    UV_HTTP_TIMEOUT=60

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked \
    --no-install-project --no-editable

COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable


FROM python-base AS runtime

# The supported vendor runtime has no pip/bootstrap installer. Keep the package
# database for scanning and the complete application environment from the builder.

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY --from=builder --chown=10001:10001 \
    /app/.venv /app/.venv

COPY --chown=10001:10001 \
    alembic.ini ./

COPY --chown=10001:10001 \
    alembic ./alembic

USER 10001:10001

EXPOSE 8080

ENTRYPOINT ["python", "-m", "opsproof_control"]

CMD ["api"]
