from __future__ import annotations

from collections import OrderedDict
import hashlib
import time


class ResponseLRUCache:
    """Simple LRU cache for `match_jobs` responses."""

    def __init__(self, max_size: int = 128, ttl_sec: int = 300) -> None:
        self._store: OrderedDict[str, tuple[object, float]] = OrderedDict()
        self._max_size = max(1, max_size)
        self._ttl = float(ttl_sec)

    @staticmethod
    def make_key(**kwargs: object) -> str:
        raw = "|".join(f"{k}={v}" for k, v in sorted([(str(k), str(v)) for k, v in kwargs.items()]))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, key: str) -> object | None:
        if key not in self._store:
            return None
        response, ts = self._store[key]
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return response

    def set(self, key: str, response: object) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (response, time.monotonic())
        if len(self._store) > self._max_size:
            self._store.popitem(last=False)

