"""One connection pool per independent workload process."""

from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings


@lru_cache
def pool() -> ConnectionPool:
    return ConnectionPool(
        conninfo=settings().database_url,
        min_size=1,
        max_size=4,
        timeout=5,
        kwargs={
            "row_factory": dict_row,
            "connect_timeout": 3,
        },
        open=True,
    )
