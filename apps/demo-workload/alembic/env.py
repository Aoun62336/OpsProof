"""Run migrations using the configured PostgreSQL connection."""

import os

from sqlalchemy import create_engine, pool

from alembic import context

config = context.config

database_url = os.environ["OPSPROOF_DATABASE_URL"].replace(
    "postgresql://",
    "postgresql+psycopg://",
    1,
)


def run_migrations_online() -> None:
    engine = create_engine(
        database_url,
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
