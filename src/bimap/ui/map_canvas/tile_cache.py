"""On-disk tile cache using diskcache."""

from __future__ import annotations

from pathlib import Path

from bimap.config import TILE_CACHE_DIR, TILE_CACHE_EXPIRE_DAYS, TILE_CACHE_SIZE_BYTES


class TileCache:
    """Thread-safe on-disk LRU cache for map tiles (PNG bytes)."""

    def __init__(self) -> None:
        import diskcache
        self._cache = diskcache.Cache(
            str(TILE_CACHE_DIR),
            size_limit=TILE_CACHE_SIZE_BYTES,
        )
        self._expire = TILE_CACHE_EXPIRE_DAYS * 86_400   # seconds

    def get(self, key: str) -> bytes | None:
        return self._cache.get(key)

    def put(self, key: str, data: bytes) -> None:
        self._cache.set(key, data, expire=self._expire)

    def clear(self) -> None:
        self._cache.clear()

    def close(self) -> None:
        self._cache.close()
