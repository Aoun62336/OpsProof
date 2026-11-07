"""Entry points for independently running workload processes."""

import argparse
import logging

import uvicorn

from .db import pool
from .dispatcher import run as run_dispatcher
from .shutdown import lifecycle
from .worker import run as run_worker


def main() -> None:
    parser = argparse.ArgumentParser(prog="opsproof-demo")
    parser.add_argument(
        "service",
        choices=["api", "dispatcher", "worker"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s %(levelname)s %(name)s %(message)s"),
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not any(isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root_logger.addHandler(console_handler)

    if args.service == "api":
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
