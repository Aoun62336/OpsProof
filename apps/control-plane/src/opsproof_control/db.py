"""Independent connection pools for each control-plane process."""

from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from redis import Redis

from .config import settings


@lru_cache
def pool() -> ConnectionPool:
    return ConnectionPool(
        conninfo=settings().database_url,
        min_size=1,
        max_size=3,
        timeout=5,
        kwargs={
            "row_factory": dict_row,
            "connect_timeout": 3,
        },
        open=False,
    )


@lru_cache
def redis_client() -> Redis:
    return Redis.from_url(
        settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=4,
    )
