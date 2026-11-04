"""Database migrations for the independent control-plane store."""

import os

from sqlalchemy import create_engine, pool

from alembic import context


def run_migrations_online() -> None:
    raw_url = os.environ["OPSPROOF_CONTROL_DATABASE_URL"]
    url = raw_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )
    engine = create_engine(
        url,
        poolclass=pool.NullPool,
    )
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=None,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations_online()
