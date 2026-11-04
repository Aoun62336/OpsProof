"""Entry points for independently running workload processes."""

import argparse
import logging

import uvicorn

from .dispatcher import run as run_dispatcher
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

    if args.service == "api":
        uvicorn.run(
            "opsproof_demo.api:app",
            host="0.0.0.0",
            port=8080,
            workers=1,
        )
    elif args.service == "dispatcher":
        run_dispatcher()
    elif args.service == "worker":
        run_worker()


if __name__ == "__main__":
    main()
