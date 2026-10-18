"""Single place that builds the Redis connection."""

import redis

from liquid_atm_quant.config import Settings


def make_redis(settings: Settings) -> redis.Redis:
    # decode_responses=True: we store JSON text and small strings, never binary blobs.
    return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=5)
