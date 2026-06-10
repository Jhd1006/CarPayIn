import os

from redis import Redis

_PMS_REDIS_URL = os.getenv("PMS_REDIS_URL", "redis://localhost:6379/1")

redis_client = Redis.from_url(_PMS_REDIS_URL, decode_responses=True)
