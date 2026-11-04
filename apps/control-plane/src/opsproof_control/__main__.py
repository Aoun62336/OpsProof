"""Entry points for independently deployed control-plane processes."""

import argparse
import logging

import uvicorn

from .action import run as run_action
from .evidence import run as run_evidence
from .streams import dispatcher


def main() -> None:
    parser = argparse.ArgumentParser(prog="opsproof-control")
    parser.add_argument(
        "role",
        choices=[
            "api",
            "dispatch",
            "evidence",
            "action",
        ],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s %(levelname)s %(name)s %(message)s"),
    )

    if args.role == "api":
        uvicorn.run(
            "opsproof_control.api:app",
            host="0.0.0.0",
            port=8080,
            workers=1,
        )
    elif args.role == "dispatch":
        dispatcher()
    elif args.role == "evidence":
        run_evidence()
    elif args.role == "action":
        run_action()


if __name__ == "__main__":
    main()
