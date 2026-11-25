"""Entry points for independently running workload processes."""

import argparse

import uvicorn

from .db import pool
from .dispatcher import run as run_dispatcher
from .shutdown import lifecycle
from .telemetry import configure_logging
from .worker import run as run_worker


def main() -> None:
    parser = argparse.ArgumentParser(prog="opsproof-demo")
    parser.add_argument(
        "service",
        choices=["api", "dispatcher", "worker", "fixture"],
    )
    args = parser.parse_args()

    configure_logging()

    if args.service == "fixture":
        uvicorn.run(
            "opsproof_demo.downstream_fixture:app",
            host="0.0.0.0",
            port=8080,
            workers=1,
        )
    elif args.service == "api":
        uvicorn.run(
            "opsproof_demo.api:app",
            host="0.0.0.0",
            port=8080,
            workers=1,
        )
    else:
        with lifecycle():
            try:
                if args.service == "dispatcher":
                    run_dispatcher()
                else:
                    run_worker()
            finally:
                if pool.cache_info().currsize:
                    pool().close()


if __name__ == "__main__":
    main()
