"""Non-mutating M6 trial coordinator.

Currently handles durable source-contract preflight bookkeeping and expiry only.
It has no Kubernetes credentials, fault adapters, or capability to claim success.
"""

import logging

from .config import settings
from .db import pool
from .m6_access import require_application_role
from .m6_trial_store import claim_preflight, expire_dispatched_trials, expire_uninjected_approvals
from .shutdown import stopping

logger = logging.getLogger(__name__)


def tick() -> tuple[bool, int]:
    with pool().connection() as conn:
        trial_id = claim_preflight(conn)
        expired = expire_uninjected_approvals(conn)
        expire_dispatched_trials(conn)
    if trial_id:
        logger.info("M6 source preflight recorded: %s", trial_id)
    if expired:
        logger.warning("M6 approvals expired without injection: %s", expired)
    return trial_id is not None, expired


def run() -> None:
    if not settings().m6_enabled:
        raise RuntimeError("M6 trial coordinator is disabled")
    with pool().connection() as conn:
        require_application_role(conn)
    logger.info("M6 trial ledger worker started; fault injection is NOT enabled")
    while not stopping.is_set():
        try:
            tick()
        except Exception:
            logger.exception("M6 trial ledger processing error; will retry")
        stopping.wait(2)
