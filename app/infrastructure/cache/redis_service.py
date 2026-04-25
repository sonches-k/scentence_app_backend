import json
from typing import Any, Optional

import redis as redis_lib

from app.core.interfaces import ICacheService


class RedisCacheService(ICacheService):

    def __init__(self, url: str):
        self._client = redis_lib.from_url(url, decode_responses=True)

    def get(self, key: str) -> Optional[Any]:
        try:
            value = self._client.get(key)
            return json.loads(value) if value is not None else None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception:
            pass

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
