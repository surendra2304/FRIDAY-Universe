"""
Thread-safe in-memory TTL/LRU Cache for Project FORGE.
Provides fast in-memory caching with time-to-live expiration and LRU eviction.
"""

from __future__ import annotations

import asyncio
import functools
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CacheItem:
    """Wraps cached value with creation and expiration timestamp."""

    __slots__ = ("value", "expires_at", "last_accessed")

    def __init__(self, value: Any, ttl_seconds: float):
        now = datetime.now(timezone.utc).timestamp()
        self.value = value
        self.expires_at = now + ttl_seconds if ttl_seconds > 0 else float("inf")
        self.last_accessed = now

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at


class TTLCache:
    """
    Thread-safe, high-performance in-memory cache with TTL and LRU eviction.
    """

    def __init__(self, maxsize: int = 1024, default_ttl: float = 300.0):
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self._lock = threading.RLock()
        self._store: OrderedDict[str, CacheItem] = OrderedDict()

    def _purge_expired(self, now: float) -> None:
        """Internal helper to prune expired entries."""
        expired_keys = [k for k, item in self._store.items() if item.is_expired(now)]
        for k in expired_keys:
            self._store.pop(k, None)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value by key if present and not expired."""
        with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            item = self._store.get(key)
            if item is None:
                return default
            if item.is_expired(now):
                self._store.pop(key, None)
                return default
            # Move to end for LRU tracking
            item.last_accessed = now
            self._store.move_to_end(key)
            return item.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store value with key and optional custom TTL in seconds."""
        effective_ttl = ttl if ttl is not None else self.default_ttl
        with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            self._purge_expired(now)

            # Evict oldest entry if at capacity
            if len(self._store) >= self.maxsize and key not in self._store:
                self._store.popitem(last=False)

            item = CacheItem(value, effective_ttl)
            self._store[key] = item
            self._store.move_to_end(key)

    def delete(self, key: str) -> bool:
        """Remove key from cache if present."""
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> None:
        """Wipe all cached entries."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            self._purge_expired(now)
            return len(self._store)

    def contains(self, key: str) -> bool:
        return self.get(key) is not None


# Global default cache instance
memory_cache = TTLCache(maxsize=2048, default_ttl=300.0)


def cached(ttl: float = 300.0, maxsize: int = 512, cache_instance: TTLCache | None = None):
    """
    Decorator for caching function or coroutine returns based on stringifiable arguments.
    """
    cache = cache_instance or TTLCache(maxsize=maxsize, default_ttl=ttl)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = f"{fn.__qualname__}:{str(args)}:{str(sorted(kwargs.items()))}"
                hit = cache.get(key)
                if hit is not None:
                    return hit
                result = await fn(*args, **kwargs)
                cache.set(key, result, ttl=ttl)
                return result
            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = f"{fn.__qualname__}:{str(args)}:{str(sorted(kwargs.items()))}"
            hit = cache.get(key)
            if hit is not None:
                return hit
            result = fn(*args, **kwargs)
            cache.set(key, result, ttl=ttl)
            return result
        return sync_wrapper

    return decorator
