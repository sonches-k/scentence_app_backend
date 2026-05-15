import json
import logging
from typing import Any, Optional

import redis as redis_lib

from app.core.interfaces import ICacheService

logger = logging.getLogger(__name__)


class RedisCacheService(ICacheService):

    def __init__(self, url: str):
        self._client = redis_lib.from_url(url, decode_responses=True)

    def get(self, key: str) -> Optional[Any]:
        try:
            value = self._client.get(key)
            return json.loads(value) if value is not None else None
        except Exception as exc:
            logger.warning("Redis GET failed for key=%r: %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception as exc:
            logger.warning("Redis SET failed for key=%r: %s", key, exc)

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception:
            pass

    def clear(self) -> None:
        try:
            self._client.flushdb()
        except Exception:
            pass
