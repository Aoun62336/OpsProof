"""Entry points for independently deployed control-plane processes."""

import argparse

import uvicorn

from .action import run as run_action
from .db import pool, redis_client
from .evidence import run as run_evidence
from .shutdown import lifecycle
from .streams import dispatcher
from .telemetry import configure_logging
from .trial_worker import run as run_trial


def main() -> None:
    parser = argparse.ArgumentParser(prog="opsproof-control")
    parser.add_argument(
        "role",
        choices=[
            "api",
            "dispatch",
            "evidence",
            "action",
            "trial",
        ],
    )
    args = parser.parse_args()

    configure_logging()

    if args.role == "api":
        uvicorn.run(
            "opsproof_control.api:app",
            host="0.0.0.0",
            port=8080,
            workers=1,
        )
    else:
        with lifecycle():
            try:
                runners = {
                    "dispatch": dispatcher,
                    "evidence": run_evidence,
                    "action": run_action,
                    "trial": run_trial,
                }
                runners[args.role]()
            finally:
                if redis_client.cache_info().currsize:
                    redis_client().close()
                if pool.cache_info().currsize:
                    pool().close()


if __name__ == "__main__":
    main()
