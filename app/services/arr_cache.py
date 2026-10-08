"""Process-local TTL cache for *arr API payloads (single uvicorn worker)."""

import time
from collections.abc import Awaitable, Callable
from typing import Any


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    async def get_or_set(
        self,
        key: str,
        ttl: float,
        factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        now = time.monotonic()
        hit = self._store.get(key)
        if hit is not None and hit[0] > now:
            return hit[1]
        value = await factory()
        self._store[key] = (now + ttl, value)
        return value

    def invalidate(self, prefix: str | None = None) -> None:
        if prefix is None:
            self._store.clear()
            return
        for key in [k for k in self._store if k.startswith(prefix)]:
            del self._store[key]

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def __len__(self) -> int:
        return len(self._store)


arr_cache = TTLCache()
