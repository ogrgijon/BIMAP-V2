"""
Map canvas widget — renders OSM tiles + zone/keypoint/annotation overlays.

Architecture:
- TileWidget (QWidget) — top-level composite
  ├─ TileFetcher (QThread) — downloads tiles from network
  ├─ TileCache — on-disk tile cache
  ├─ OverlayRenderer — paints zones, keypoints, annotations
  └─ InteractionHandler — translates mouse/keyboard events → tool actions
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QRunnable, Qt, QThread, QThreadPool, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
import requests

from bimap.config import HTTP_HEADERS, TILE_PROVIDERS, TILE_SIZE
from bimap.engine.tile_math import TileCoord
from bimap.ui.map_canvas.tile_cache import TileCache

if TYPE_CHECKING:
    pass

# Singleton cache shared across all canvases
_tile_cache: TileCache | None = None


def get_tile_cache() -> TileCache:
    global _tile_cache
    if _tile_cache is None:
        _tile_cache = TileCache()
    return _tile_cache


# ── Tile fetch runnable ────────────────────────────────────────────────────────

# Cancellation event — set() to stop all pending tile fetches immediately
_cancel_event: threading.Event = threading.Event()


def stop_all_tile_fetches() -> None:
    """Prevent queued tile jobs from doing more work during application shutdown."""
    _cancel_event.set()


class TileFetchSignals(QObject):
    tile_ready = pyqtSignal(int, int, int, QPixmap)    # x, y, z, pixmap
    tile_error = pyqtSignal(int, int, int)


class TileFetchRunnable(QRunnable):
    """Downloads a single tile in the thread pool."""

    def __init__(self, tile: TileCoord, url_template: str) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._tile = tile
        self._url_template = url_template
        self.signals = TileFetchSignals()

    def run(self) -> None:
        if _cancel_event.is_set():
            return
        # Keep a local Python reference — the QRunnable's C++ side may be
        # deleted by the thread pool before the except/finally block runs,
        # which would make `self.signals` a dangling pointer.
        signals = self.signals
        t = self._tile
        cache = get_tile_cache()
        cache_key = f"{self._url_template}_{t.z}_{t.x}_{t.y}"
        cached = cache.get(cache_key)
        if cached:
            pm = _bytes_to_pixmap(cached)
            if pm and not pm.isNull():
                try:
                    signals.tile_ready.emit(t.x, t.y, t.z, pm)
                except RuntimeError:
                    pass
                return

        url = (
            self._url_template
            .replace("{z}", str(t.z))
            .replace("{x}", str(t.x))
            .replace("{y}", str(t.y))
        )
        data: bytes | None = None
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=5)
            resp.raise_for_status()
            data = resp.content
        except requests.RequestException:
            pass

        if data is None:
            # Network unavailable — try serving a parent tile from the disk cache
            # (covers tiles pre-saved via "Work Offline" or previously downloaded).
            for parent_z in range(t.z - 1, max(t.z - 4, 0), -1):
                diff = t.z - parent_z
                p_key = f"{self._url_template}_{parent_z}_{t.x >> diff}_{t.y >> diff}"
                p_data = cache.get(p_key)
                if p_data:
                    p_pm = _bytes_to_pixmap(p_data)
                    if p_pm and not p_pm.isNull():
                        from bimap.config import TILE_SIZE
                        scale = 2 ** diff
                        src_size = max(TILE_SIZE // scale, 1)
                        col = t.x & (scale - 1)
                        row = t.y & (scale - 1)
                        cropped = p_pm.copy(col * src_size, row * src_size,
                                            src_size, src_size)
                        scaled = cropped.scaled(
                            TILE_SIZE, TILE_SIZE,
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        try:
                            signals.tile_ready.emit(t.x, t.y, t.z, scaled)
                        except RuntimeError:
                            pass
                        return
            try:
                signals.tile_error.emit(t.x, t.y, t.z)
            except RuntimeError:
                pass
            return

        cache.put(cache_key, data)
        pm = _bytes_to_pixmap(data)
        try:
            if pm and not pm.isNull():
                signals.tile_ready.emit(t.x, t.y, t.z, pm)
            else:
                signals.tile_error.emit(t.x, t.y, t.z)
        except RuntimeError:
            pass


def _bytes_to_pixmap(data: bytes) -> QPixmap:
    img = QImage()
    img.loadFromData(data)
    return QPixmap.fromImage(img)
