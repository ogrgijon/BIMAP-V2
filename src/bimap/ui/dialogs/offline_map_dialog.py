"""Offline map dialog — download and cache map tiles for a selected region.

Flow:
  1. User sets a bounding box (uses current map view as default).
  2. Selects zoom levels (min / max).
  3. App calculates tile count and warns if over the safety limit.
  4. Download starts via the existing TileFetchRunnable / TileCache pipeline.
     Tiles are stored in the on-disk diskcache; offline use is automatic.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QRunnable, QThread, QThreadPool, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button

if TYPE_CHECKING:
    from bimap.ui.map_canvas.tile_widget import TileWidget

_MAX_TILES = 50_000   # hard safety limit


def _tile_count(lat_min: float, lat_max: float,
                lon_min: float, lon_max: float,
                zoom_min: int, zoom_max: int) -> int:
    """Estimate the number of OSM tiles covering the bounding box across zoom levels."""
    from bimap.engine.tile_math import lat_lon_to_tile
    total = 0
    for z in range(zoom_min, zoom_max + 1):
        t0 = lat_lon_to_tile(lat_max, lon_min, z)   # top-left tile (higher lat = lower y tile)
        t1 = lat_lon_to_tile(lat_min, lon_max, z)   # bottom-right tile
        nx = abs(t1.x - t0.x) + 1
        ny = abs(t1.y - t0.y) + 1
        total += nx * ny
    return total


def _iter_tiles(lat_min: float, lat_max: float,
                lon_min: float, lon_max: float,
                zoom_min: int, zoom_max: int):
    """Yield (x, y, z) tuples for all tiles in the bounding box + zoom range."""
    from bimap.engine.tile_math import lat_lon_to_tile
    for z in range(zoom_min, zoom_max + 1):
        t0 = lat_lon_to_tile(lat_max, lon_min, z)
        t1 = lat_lon_to_tile(lat_min, lon_max, z)
        x_min, x_max = sorted([t0.x, t1.x])
        y_min, y_max = sorted([t0.y, t1.y])
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                yield x, y, z


# ── Worker ─────────────────────────────────────────────────────────────────────

class _DownloadSignals(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(int, int)  # downloaded, skipped (already cached)
    error = pyqtSignal(str)


class _DownloadWorker(QRunnable):
    """Downloads all tiles for the region in a single background runnable."""

    def __init__(self, tiles: list, url_template: str) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._tiles = tiles
        self._url_template = url_template
        self.signals = _DownloadSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        import requests
        from bimap.config import HTTP_HEADERS
        from bimap.ui.map_canvas.tile_fetcher import get_tile_cache
        import time

        cache = get_tile_cache()
        downloaded = 0
        skipped = 0

        for i, (x, y, z) in enumerate(self._tiles):
            if self._cancelled:
                break
            cache_key = f"{self._url_template}_{z}_{x}_{y}"
            if cache.get(cache_key):
                skipped += 1
            else:
                url = (
                    self._url_template
                    .replace("{z}", str(z))
                    .replace("{x}", str(x))
                    .replace("{y}", str(y))
                )
                for attempt in range(3):
                    if self._cancelled:
                        break
                    try:
                        resp = requests.get(url, headers=HTTP_HEADERS, timeout=10)
                        resp.raise_for_status()
                        cache.put(cache_key, resp.content)
                        downloaded += 1
                        break
                    except requests.RequestException:
                        if attempt == 2:
                            skipped += 1   # count as skipped on final failure
                        else:
                            time.sleep(0.4 * (2 ** attempt))

            try:
                self.signals.progress.emit(i + 1)
            except RuntimeError:
                break

        try:
            self.signals.finished.emit(downloaded, skipped)
        except RuntimeError:
            pass


# ── Dialog ─────────────────────────────────────────────────────────────────────

class OfflineMapDialog(QDialog):
    """Download and cache OSM tiles for offline use."""

    def __init__(
        self,
        canvas: "TileWidget",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Work Offline — Save Map Region"))
        self.setMinimumWidth(480)
        self._canvas = canvas
        self._worker: _DownloadWorker | None = None

        # Detect current view bounds
        w, h = canvas.width(), canvas.height()
        lat_tl, lon_tl = canvas.px_to_lat_lon(0, 0)
        lat_br, lon_br = canvas.px_to_lat_lon(w, h)
        self._default_lat_min = round(min(lat_tl, lat_br), 6)
        self._default_lat_max = round(max(lat_tl, lat_br), 6)
        self._default_lon_min = round(min(lon_tl, lon_br), 6)
        self._default_lon_max = round(max(lon_tl, lon_br), 6)
        current_zoom = getattr(canvas, "_zoom", 14)

        layout = QVBoxLayout(self)

        # ── Bounding box ──────────────────────────────────────────────────────
        bbox_grp = QGroupBox(t("Bounding Box"))
        bbox_form = QFormLayout(bbox_grp)

        def _dbl(val: float, lo: float, hi: float) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setDecimals(6)
            s.setRange(lo, hi)
            s.setValue(val)
            return s

        self._lat_min = _dbl(self._default_lat_min, -90, 90)
        self._lat_max = _dbl(self._default_lat_max, -90, 90)
        self._lon_min = _dbl(self._default_lon_min, -180, 180)
        self._lon_max = _dbl(self._default_lon_max, -180, 180)

        bbox_form.addRow(t("Lat min (South):"), self._lat_min)
        bbox_form.addRow(t("Lat max (North):"), self._lat_max)
        bbox_form.addRow(t("Lon min (West):"), self._lon_min)
        bbox_form.addRow(t("Lon max (East):"), self._lon_max)

        reset_btn = QPushButton(t("Use Current View"))
        reset_btn.clicked.connect(self._reset_to_view)
        bbox_form.addRow("", reset_btn)
        layout.addWidget(bbox_grp)

        # ── Zoom levels ───────────────────────────────────────────────────────
        zoom_grp = QGroupBox(t("Zoom Levels"))
        zoom_form = QFormLayout(zoom_grp)

        self._zoom_min = QSpinBox()
        self._zoom_min.setRange(1, 19)
        self._zoom_min.setValue(max(1, current_zoom - 2))

        self._zoom_max = QSpinBox()
        self._zoom_max.setRange(1, 19)
        self._zoom_max.setValue(min(19, current_zoom))

        zoom_form.addRow(t("Min zoom:"), self._zoom_min)
        zoom_form.addRow(t("Max zoom:"), self._zoom_max)
        layout.addWidget(zoom_grp)

        # ── Estimate ──────────────────────────────────────────────────────────
        est_row = QWidget()
        est_layout = QHBoxLayout(est_row)
        est_layout.setContentsMargins(0, 4, 0, 4)
        est_btn = QPushButton(t("Estimate Tile Count"))
        est_btn.clicked.connect(self._estimate)
        self._est_label = QLabel("—")
        est_layout.addWidget(est_btn)
        est_layout.addWidget(self._est_label)
        est_layout.addStretch()
        layout.addWidget(est_row)

        # ── Progress ──────────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # ── Buttons ───────────────────────────────────────────────────────────
        self._download_btn = QPushButton(t("⬇  Download && Cache Tiles"))
        self._download_btn.clicked.connect(self._start_download)
        layout.addWidget(self._download_btn)

        self._cancel_btn = QPushButton(t("Cancel Download"))
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel_download)
        layout.addWidget(self._cancel_btn)

        bbox_close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bbox_close.rejected.connect(self.reject)
        add_dialog_help_button(bbox_close, self, "Offline Map window help")
        layout.addWidget(bbox_close)

        # Auto-estimate on change
        for w in (self._lat_min, self._lat_max, self._lon_min, self._lon_max,
                  self._zoom_min, self._zoom_max):
            w.valueChanged.connect(self._estimate)

        self._estimate()

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _reset_to_view(self) -> None:
        self._lat_min.setValue(self._default_lat_min)
        self._lat_max.setValue(self._default_lat_max)
        self._lon_min.setValue(self._default_lon_min)
        self._lon_max.setValue(self._default_lon_max)

    def _estimate(self) -> None:
        lat_min = self._lat_min.value()
        lat_max = self._lat_max.value()
        lon_min = self._lon_min.value()
        lon_max = self._lon_max.value()
        zm = self._zoom_min.value()
        zx = self._zoom_max.value()
        if lat_min >= lat_max or lon_min >= lon_max or zm > zx:
            self._est_label.setText(f"<font color='red'>{t('Invalid bounds or zoom range')}</font>")
            return
        count = _tile_count(lat_min, lat_max, lon_min, lon_max, zm, zx)
        if count > _MAX_TILES:
            colour = "red"
            note = t(" ⚠ exceeds limit — reduce zoom or area").format(limit=f"{_MAX_TILES:,}")
        elif count > _MAX_TILES // 2:
            colour = "orange"
            note = t(" (large — may take a while)")
        else:
            colour = "green"
            note = ""
        self._est_label.setText(
            f"<font color='{colour}'><b>{count:,} {t('tiles')}</b></font>{note}"
        )
        self._download_btn.setEnabled(count <= _MAX_TILES)

    def _start_download(self) -> None:
        lat_min = self._lat_min.value()
        lat_max = self._lat_max.value()
        lon_min = self._lon_min.value()
        lon_max = self._lon_max.value()
        zm = self._zoom_min.value()
        zx = self._zoom_max.value()

        if lat_min >= lat_max or lon_min >= lon_max or zm > zx:
            QMessageBox.warning(self, t("Invalid Region"), t("Please check bounds and zoom levels."))
            return

        count = _tile_count(lat_min, lat_max, lon_min, lon_max, zm, zx)
        if count > _MAX_TILES:
            QMessageBox.warning(
                self, t("Region Too Large"),
                t("This region requires {count} tiles, which exceeds the safety limit of {limit}.\n"
                  "Reduce the area or zoom range and try again.").format(
                      count=f"{count:,}", limit=f"{_MAX_TILES:,}")
            )
            return

        reply = QMessageBox.question(
            self, t("Start Download?"),
            t("Download {count} tiles for offline use?\n\nTiles already in cache will be skipped.").format(
                count=f"{count:,}"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        tiles = list(_iter_tiles(lat_min, lat_max, lon_min, lon_max, zm, zx))
        from bimap.config import TILE_PROVIDERS
        provider_key = getattr(self._canvas, "_tile_provider", "osm")
        provider_dict = TILE_PROVIDERS.get(provider_key) or list(TILE_PROVIDERS.values())[0]
        url_template: str = provider_dict["url"]

        self._worker = _DownloadWorker(tiles, url_template)
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.finished.connect(self._on_finished)

        self._progress.setRange(0, len(tiles))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._status_label.setText(t("Downloading {done} / {total} tiles…").format(done=0, total=f"{len(tiles):,}"))
        self._download_btn.setVisible(False)
        self._cancel_btn.setVisible(True)

        pool = QThreadPool.globalInstance()
        if pool is not None:
            pool.start(self._worker)

    def _cancel_download(self) -> None:
        if self._worker:
            self._worker.cancel()
        self._cancel_btn.setVisible(False)
        self._status_label.setText(t("Cancelling…"))

    def _on_progress(self, done: int) -> None:
        total = self._progress.maximum()
        self._progress.setValue(done)
        self._status_label.setText(t("Downloading {done} / {total} tiles…").format(
            done=f"{done:,}", total=f"{total:,}"))

    def _on_finished(self, downloaded: int, skipped: int) -> None:
        self._cancel_btn.setVisible(False)
        self._download_btn.setVisible(True)
        self._status_label.setText(
            t("Done — {downloaded} tiles downloaded, {skipped} already cached / skipped.").format(
                downloaded=f"{downloaded:,}", skipped=f"{skipped:,}")
        )
        self._worker = None

    def closeEvent(self, event) -> None:
        if self._worker:
            self._worker.cancel()
        super().closeEvent(event)
