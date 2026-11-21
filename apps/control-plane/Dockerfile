# syntax=docker/dockerfile:1.7

FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 \
    /uv /uvx /bin/

ENV UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked \
    --no-install-project --no-editable

COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable


FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS runtime

# Keep the complete locked application environment, without a runtime installer
# or pip's unrelated vendored libraries. Containers use an immutable filesystem.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends --only-upgrade zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall --yes pip

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
