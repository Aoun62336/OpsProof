"""Bounded demo-worker hold and idempotent recovery; no host control privileges."""

import argparse
from uuid import UUID

from redis import Redis

from .config import settings

HOLD_KEY = "opsproof:demo:worker:hold:v1"
REPLAY_PREFIX = "opsproof:demo:recovery:applied:"
DEFAULT_HOLD_SECONDS = 420
MIN_HOLD_SECONDS = 120
MAX_HOLD_SECONDS = 480
_RESUME_SCRIPT = """
if redis.call('EXISTS', KEYS[2]) == 1 then
    return 2
end
if redis.call('EXISTS', KEYS[1]) == 0 then
    return 0
end
redis.call('DEL', KEYS[1])
redis.call('SET', KEYS[2], 'applied', 'EX', 3600)
return 1
"""


def hold_state(redis: Redis) -> dict[str, bool | int]:
    ttl = redis.ttl(HOLD_KEY)
    # A non-expiring key is still a hold, but is ineligible for recovery policy.
    return {"paused": ttl != -2, "ttl_seconds": max(ttl, 0)}


def pause_worker(redis: Redis, seconds: int = DEFAULT_HOLD_SECONDS) -> bool:
    if type(seconds) is not int or not MIN_HOLD_SECONDS <= seconds <= MAX_HOLD_SECONDS:
        raise ValueError("Hold must be between 120 and 480 seconds")
    return bool(redis.set(HOLD_KEY, "manual-local-fault-drill", ex=seconds, nx=True))


def resume_worker(redis: Redis, recovery_id: UUID) -> str:
    result = redis.eval(_RESUME_SCRIPT, 2, HOLD_KEY, f"{REPLAY_PREFIX}{recovery_id}")
    return {0: "not_paused", 1: "applied", 2: "replayed"}[result]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["pause", "status"])
    parser.add_argument("--seconds", type=int, default=DEFAULT_HOLD_SECONDS)
    args = parser.parse_args()
    with Redis.from_url(settings().redis_url, socket_timeout=3) as redis:
        if args.command == "pause":
            try:
                created = pause_worker(redis, args.seconds)
            except ValueError as exc:
                parser.error(str(exc))
            if not created:
                raise SystemExit("Existing hold preserved; no expiry extension applied.")
            print(f"Bounded demo-worker hold created: {args.seconds} seconds")
        else:
            state = hold_state(redis)
            print(f"Worker hold active: {state['paused']}")
            print(f"Remaining TTL: {state['ttl_seconds']} seconds")


if __name__ == "__main__":
    main()
