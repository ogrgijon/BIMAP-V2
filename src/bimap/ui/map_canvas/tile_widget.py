"""
TileWidget — the central map canvas that renders tiles and all overlays.
"""

from __future__ import annotations

import math
from typing import Any

from PyQt6.QtCore import (
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QContextMenuEvent,
    QCursor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import QMenu, QWidget

from bimap.config import (
    MAX_ZOOM,
    MIN_ZOOM,
    TILE_PROVIDERS,
    TILE_SIZE,
)
from bimap.engine.tile_math import (
    lat_lon_to_pixel,
    pixel_to_lat_lon,
    visible_tiles,
)
from bimap.ui.map_canvas.tile_fetcher import TileFetchRunnable, get_tile_cache
from bimap.ui.map_canvas.overlay_renderer import OverlayRenderer
from bimap.ui.map_canvas.interaction import InteractionHandler, ToolMode
from bimap.i18n import t


class TileWidget(QWidget):
    """
    The main interactive map canvas.

    Signals
    -------
    viewport_changed(lat, lon, zoom) - emitted on every pan/zoom
    element_selected(element_type, element_id) - user clicked a zone/keypoint
    draw_finished(element_type, data) - user finished drawing a new element
    coordinates_changed(lat, lon) - mouse-move coordinate update for status bar
    """

    viewport_changed = pyqtSignal(float, float, int)
    element_selected = pyqtSignal(str, str)
    draw_finished = pyqtSignal(str, object)
    coordinates_changed = pyqtSignal(float, float)
    context_action_requested = pyqtSignal(str, str, str)    # action, etype, eid
    multi_select_finished = pyqtSignal(list)
    element_move_dropped = pyqtSignal(str, str, float, float)
    add_annotation_requested = pyqtSignal(str, float, float)  # ann_type, lat, lon
    open_extension_requested = pyqtSignal(str, str)           # etype, eid
    element_rotated = pyqtSignal(str, str, float)             # etype, eid, degrees
    network_status_changed = pyqtSignal(bool)                 # True = online, False = offline
    data_feature_selected = pyqtSignal(str, int)              # source_id, row_index
    tool_changed = pyqtSignal(str)                            # effective ToolMode value

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        # Viewport state
        self._center_lat: float = 40.4168
        self._center_lon: float = -3.7038
        self._zoom: int = 12
        self._tile_provider: str = "osm_standard"

        # Tile storage keyed by (x, y, z)
        self._tiles: dict[tuple[int, int, int], QPixmap] = {}
        self._pending: set[tuple[int, int, int]] = set()
        # Tiles that failed to load (not re-requested until provider/viewport changes)
        self._failed: set[tuple[int, int, int]] = set()

        # Online/offline detection
        self._consecutive_errors: int = 0
        self._is_online: bool = True

        # Thread pool for tile fetching
        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(6)

        # Debounce timer — fires _refresh_tiles() 50ms after last pan event
        self._pan_debounce_timer = QTimer(self)
        self._pan_debounce_timer.setSingleShot(True)
        self._pan_debounce_timer.setInterval(50)
        self._pan_debounce_timer.timeout.connect(self._refresh_tiles)

        # Overlay renderer — draws zones, keypoints, annotations
        self._overlay = OverlayRenderer()

        # Interaction handler — tool modes, drawing, selection
        self._interaction = InteractionHandler(self)
        self._interaction.request_repaint.connect(self.update)
        self._interaction.draw_finished.connect(self._on_draw_finished)
        self._interaction.element_selected.connect(self.element_selected)
        self._interaction.multi_select_finished.connect(self.multi_select_finished)
        self._interaction.element_move_dropped.connect(self.element_move_dropped)
        self._interaction.open_extension_requested.connect(self.open_extension_requested)
        self._interaction.element_rotated.connect(self.element_rotated)

        # Drag state
        self._drag_start: QPoint | None = None
        self._drag_center_lat: float = self._center_lat
        self._drag_center_lon: float = self._center_lon

        # Overlay visibility flags (controlled via set_overlay_flags)
        self._show_scale_bar: bool = True
        self._show_north_arrow: bool = True
        self._show_grid: bool = False
        self._grid_scale: float = 1.0

        # Live-feed positions: layer_id → list of position dicts
        self._live_positions: dict[str, list[dict]] = {}

        # Data-layer rows: source_id → list of row dicts (from DataSource.fetch)
        self._data_layer_rows: dict[str, list[dict]] = {}

        # Project reference (set externally)
        self._project = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_project(self, project: Any) -> None:
        self._project = project
        self.set_viewport(
            project.map_state.center_lat,
            project.map_state.center_lon,
            project.map_state.zoom,
        )
        self.set_tile_provider(project.map_state.tile_provider)

    def set_viewport(self, lat: float, lon: float, zoom: int) -> None:
        self._center_lat = lat
        self._center_lon = lon
        provider_max = TILE_PROVIDERS.get(self._tile_provider, {}).get("max_zoom", MAX_ZOOM)
        effective_max = min(provider_max, self._max_zoom_for_10m())
        self._zoom = max(MIN_ZOOM, min(effective_max, zoom))
        # Clear failed tiles when the viewport changes so offline-cached tiles
        # are retried after a pan/zoom (the offline region may now be available)
        self._failed.clear()
        self._refresh_tiles()
        self.update()
        self.viewport_changed.emit(self._center_lat, self._center_lon, self._zoom)

    def set_tile_provider(self, provider_key: str) -> None:
        if provider_key in TILE_PROVIDERS:
            self._tile_provider = provider_key
            self._tiles.clear()
            self._pending.clear()
            self._failed.clear()
            self._refresh_tiles()
            self.update()

    def set_overlay_flags(
        self, show_scale_bar: bool, show_north_arrow: bool, show_grid: bool = False
    ) -> None:
        """Toggle scale bar, north arrow, and coordinate grid overlays."""
        self._show_scale_bar = show_scale_bar
        self._show_north_arrow = show_north_arrow
        self._show_grid = show_grid
        self.update()

    def set_grid_scale(self, scale: float) -> None:
        """Set the grid density multiplier (0.5 = fine, 1.0 = normal, 2.0 = coarse)."""
        self._grid_scale = max(0.1, scale)
        self.update()

    def update_data_layer_rows(self, source_id: str, rows: list[dict]) -> None:
        """Store the latest fetched rows for a data layer and repaint."""
        self._data_layer_rows[source_id] = rows
        self.update()

    def fit_to_extent(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        padding: float = 0.1,
    ) -> None:
        """Fly the viewport to best-fit the given bounding box.

        *padding* is a fraction of the bbox span added on each side (default 10%).
        """
        import math

        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon
        if lat_span <= 0 or lon_span <= 0:
            self.set_viewport(
                (min_lat + max_lat) / 2,
                (min_lon + max_lon) / 2,
                self._zoom,
            )
            return

        # Add padding
        lat_span *= 1 + 2 * padding
        lon_span *= 1 + 2 * padding
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2

        w, h = max(self.width(), 400), max(self.height(), 300)
        # Zoom that fits horizontally
        zoom_x = math.floor(math.log2(360.0 * w / TILE_SIZE / max(lon_span, 1e-6)))
        # Zoom that fits vertically (approximate: mercator lat compression)
        zoom_y = math.floor(math.log2(170.0 * h / TILE_SIZE / max(lat_span, 1e-6)))
        zoom = max(1, min(zoom_x, zoom_y, 17))
        self.set_viewport(center_lat, center_lon, zoom)

    def clear_data_layer_rows(self, source_id: str) -> None:
        """Remove stored rows for a data layer and repaint."""
        self._data_layer_rows.pop(source_id, None)
        self.update()

    # ── Data feature selection ─────────────────────────────────────────────────

    def hit_test_data_layers(self, px: float, py: float) -> tuple[str, int] | None:
        """Check if the given pixel coordinates hit any visible data layer feature.
        
        Returns (source_id, row_index) of the hit feature, or None.
        """
        return self._overlay.hit_test_data_feature(px, py)

    def select_data_feature(self, source_id: str | None, row_index: int | None) -> None:
        """Set the selected data feature and trigger repaint with highlight."""
        self._overlay.set_selected_data_feature(source_id, row_index)
        if source_id is not None and row_index is not None:
            self.data_feature_selected.emit(source_id, row_index)
        self.update()

    def clear_data_feature_selection(self) -> None:
        """Clear the selected data feature."""
        self._overlay.set_selected_data_feature(None, None)
        self.update()

    # ── Live positions ─────────────────────────────────────────────────────────

    def update_live_positions(self, layer_id: str, positions: list[dict]) -> None:
        """Store latest polled positions for a layer and repaint."""
        self._live_positions[layer_id] = positions
        self.update()

    def clear_live_positions(self, layer_id: str) -> None:
        """Remove stored positions for a layer and repaint."""
        self._live_positions.pop(layer_id, None)
        self.update()

    def set_tool(self, mode: ToolMode) -> None:
        self._interaction.set_tool(mode)
        cursor_map = {
            ToolMode.SELECT: Qt.CursorShape.ArrowCursor,
            ToolMode.PAN: Qt.CursorShape.OpenHandCursor,
            ToolMode.DRAW_POLYGON: Qt.CursorShape.CrossCursor,
            ToolMode.DRAW_RECTANGLE: Qt.CursorShape.CrossCursor,
            ToolMode.DRAW_CIRCLE: Qt.CursorShape.CrossCursor,
            ToolMode.DRAW_KEYPOINT: Qt.CursorShape.CrossCursor,
            ToolMode.DRAW_TEXT: Qt.CursorShape.IBeamCursor,
            ToolMode.MAGIC_WAND: Qt.CursorShape.CrossCursor,
            ToolMode.MOVE_ELEMENT: Qt.CursorShape.SizeAllCursor,
            ToolMode.ROTATE_ELEMENT: Qt.CursorShape.CrossCursor,
            ToolMode.MEASURE: Qt.CursorShape.CrossCursor,
            ToolMode.DIMENSION: Qt.CursorShape.CrossCursor,
        }
        self.setCursor(QCursor(cursor_map.get(mode, Qt.CursorShape.ArrowCursor)))
        self.tool_changed.emit(mode.value)

    def _on_draw_finished(self, element_type: str, element: Any) -> None:
        """Return to selection mode after creating a map element."""
        self.set_tool(ToolMode.SELECT)
        self.draw_finished.emit(element_type, element)

    @property
    def center_lat(self) -> float:
        return self._center_lat

    @property
    def center_lon(self) -> float:
        return self._center_lon

    @property
    def zoom(self) -> int:
        return self._zoom

    @property
    def tile_provider(self) -> str:
        return self._tile_provider

    @property
    def interaction(self) -> InteractionHandler:
        return self._interaction

    def lat_lon_to_px(self, lat: float, lon: float) -> QPointF:
        p = lat_lon_to_pixel(lat, lon, self._center_lat, self._center_lon,
                             self._zoom, self.width(), self.height())
        return QPointF(p.px, p.py)

    def px_to_lat_lon(self, x: float, y: float) -> tuple[float, float]:
        return pixel_to_lat_lon(x, y, self._center_lat, self._center_lon,
                                self._zoom, self.width(), self.height())

    # ── Painting ───────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Draw tiles
        self._paint_tiles(painter)

        # 2. Draw zone/keypoint/annotation overlays
        if self._project:
            ctx_render = (
                self._center_lat,
                self._center_lon,
                self._zoom,
                self.width(),
                self.height(),
            )
            preview_position = (
                self._interaction.move_preview_position(self)
                if self._interaction._move_dragging else None
            )
            self._overlay.render(
                painter,
                self._project,
                *ctx_render,
                selected_type=self._interaction.selected_type or "",
                selected_id=self._interaction.selected_id or "",
                multi_selected=self._interaction.multi_selected,
                delimitation_polygon=self._project.map_state.delimitation_polygon,
                show_scale_bar=self._show_scale_bar,
                show_north_arrow=self._show_north_arrow,
                show_grid=self._show_grid,
                grid_scale=self._grid_scale,
                live_layers=self._project.live_layers,
                live_positions=self._live_positions,
                data_layers=getattr(self._project, "data_layers", []),
                data_layer_rows=self._data_layer_rows,
                moving_element=(
                    self._interaction._move_element_type,
                    self._interaction._move_element_id,
                    *preview_position,
                ) if preview_position else None,
            )

        # 3. Draw in-progress drawing preview
        self._interaction.paint_preview(painter, self)

        # 4. Attribution text
        self._paint_attribution(painter)

        painter.end()

    def _paint_tiles(self, painter: QPainter) -> None:
        tiles = visible_tiles(
            self._center_lat, self._center_lon, self._zoom,
            self.width(), self.height()
        )
        provider_max = TILE_PROVIDERS.get(self._tile_provider, {}).get("max_zoom", MAX_ZOOM)
        beyond_server_max = self._zoom > provider_max
        for tile_coord, px, py in tiles:
            key = (tile_coord.x, tile_coord.y, tile_coord.z)
            pm = self._tiles.get(key)
            if pm:
                painter.drawPixmap(px, py, pm)
            else:
                # When zoomed beyond the tile server's max, scale up a cached
                # parent tile rather than showing an empty grey square.
                fallback = None
                if beyond_server_max:
                    fallback = self._scaled_fallback_tile(
                        tile_coord.x, tile_coord.y, tile_coord.z, provider_max
                    )
                if fallback:
                    painter.drawPixmap(px, py, fallback)
                else:
                    # Draw placeholder and schedule a fetch (will return an
                    # error at server-max zoom which _on_tile_error handles).
                    painter.fillRect(px, py, TILE_SIZE, TILE_SIZE, QColor(220, 220, 220))
                    self._request_tile(tile_coord)

    def _paint_attribution(self, painter: QPainter) -> None:
        provider = TILE_PROVIDERS.get(self._tile_provider, {})
        attr = provider.get("attribution", "")
        if not attr:
            return
        painter.setFont(QFont("Arial", 9))
        painter.setPen(QColor(60, 60, 60, 200))
        fm = painter.fontMetrics()
        rect = QRect(0, self.height() - 18, self.width() - 4, 16)
        painter.fillRect(rect, QColor(255, 255, 255, 150))
        painter.drawText(rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, attr)

    # ── Tile fetching ──────────────────────────────────────────────────────────

    def _refresh_tiles(self) -> None:
        tiles = visible_tiles(
            self._center_lat, self._center_lon, self._zoom,
            self.width(), self.height()
        )
        for tile_coord, _, _ in tiles:
            key = (tile_coord.x, tile_coord.y, tile_coord.z)
            if key not in self._tiles and key not in self._failed:
                self._request_tile(tile_coord)

    def _request_tile(self, tile: "TileCoord") -> None:
        key = (tile.x, tile.y, tile.z)
        if key in self._pending or key in self._tiles or key in self._failed:
            return
        self._pending.add(key)
        url_template = TILE_PROVIDERS[self._tile_provider]["url"]
        runnable = TileFetchRunnable(tile, url_template)
        runnable.signals.tile_ready.connect(self._on_tile_ready)
        runnable.signals.tile_error.connect(self._on_tile_error)
        self._thread_pool.start(runnable)

    def _on_tile_ready(self, x: int, y: int, z: int, pm: QPixmap) -> None:
        key = (x, y, z)
        self._pending.discard(key)
        self._consecutive_errors = 0
        if not self._is_online:
            self._is_online = True
            self.network_status_changed.emit(True)
        if z == self._zoom:   # only store if still relevant zoom
            self._tiles[key] = pm
            # LRU eviction: keep at most 300 tiles in memory
            if len(self._tiles) > 300:
                for k in list(self._tiles.keys())[:100]:
                    del self._tiles[k]
            self.update()

    def _on_tile_error(self, x: int, y: int, z: int) -> None:
        key = (x, y, z)
        self._pending.discard(key)
        self._consecutive_errors += 1
        if self._consecutive_errors >= 3 and self._is_online:
            self._is_online = False
            self.network_status_changed.emit(False)
        # Try to synthesise a scaled-up pixmap from a cached lower-zoom parent
        # tile (checks up to 4 levels up, in both memory and disk cache).
        if z == self._zoom:   # only bother if the error is for the current view
            fallback = self._scaled_fallback_tile(x, y, z, max(z - 4, 1))
            if fallback:
                self._tiles[key] = fallback
                self.update()
            else:
                # Mark as failed so we don't endlessly re-request when offline
                self._failed.add(key)

    def refresh_tiles(self) -> None:
        """Clear the failed-tile cache and repaint. Call after restoring connectivity."""
        self._failed.clear()
        self._consecutive_errors = 0
        self.update()

    def _scaled_fallback_tile(
        self, x: int, y: int, z: int, max_server_zoom: int
    ) -> QPixmap | None:
        """Return a pixmap for tile (x, y, z) by cropping and scaling a
        cached ancestor tile at *max_server_zoom* (or the closest available).
        Checks both the in-memory tile dict and the on-disk cache."""
        from bimap.ui.map_canvas.tile_fetcher import get_tile_cache, _bytes_to_pixmap
        disk_cache = get_tile_cache()
        url_template = TILE_PROVIDERS[self._tile_provider]["url"]

        for parent_z in range(z - 1, max(max_server_zoom - 1, 0), -1):
            diff = z - parent_z
            scale = 2 ** diff             # parent tile covers 2^diff child tiles
            parent_x = x >> diff
            parent_y = y >> diff
            parent_pm = self._tiles.get((parent_x, parent_y, parent_z))
            if parent_pm is None:
                # check disk cache as fallback
                cache_key = f"{url_template}_{parent_z}_{parent_x}_{parent_y}"
                p_data = disk_cache.get(cache_key)
                if p_data:
                    parent_pm = _bytes_to_pixmap(p_data)
            if parent_pm is None or parent_pm.isNull():
                continue
            # Sub-tile offset within the parent
            col = x & (scale - 1)
            row = y & (scale - 1)
            src_size = TILE_SIZE // scale
            src_x = col * src_size
            src_y = row * src_size
            cropped = parent_pm.copy(src_x, src_y, max(src_size, 1), max(src_size, 1))
            return cropped.scaled(
                TILE_SIZE, TILE_SIZE,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return None

    # ── Mouse / Keyboard events ────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._interaction.mouse_press(event, self)
        if self._interaction.tool == ToolMode.PAN:
            self._drag_start = event.position().toPoint()
            self._drag_center_lat = self._center_lat
            self._drag_center_lon = self._center_lon
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        lat, lon = self.px_to_lat_lon(pos.x(), pos.y())
        self.coordinates_changed.emit(lat, lon)

        if self._drag_start and self._interaction.tool == ToolMode.PAN:
            delta = event.position().toPoint() - self._drag_start
            # Convert pixel delta back to new center lat/lon
            new_lat, new_lon = pixel_to_lat_lon(
                self.width() / 2 - delta.x(),
                self.height() / 2 - delta.y(),
                self._drag_center_lat,
                self._drag_center_lon,
                self._zoom,
                self.width(),
                self.height(),
            )
            self._center_lat = new_lat
            self._center_lon = new_lon
            self._pan_debounce_timer.start(50)
            self.update()
        else:
            self._interaction.mouse_move(event, self)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_start and self._interaction.tool == ToolMode.PAN:
            self._drag_start = None
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            self.viewport_changed.emit(self._center_lat, self._center_lon, self._zoom)
        else:
            self._interaction.mouse_release(event, self)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self._interaction.mouse_double_click(event, self)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        provider_max = TILE_PROVIDERS.get(self._tile_provider, {}).get("max_zoom", MAX_ZOOM)
        scale_max = self._max_zoom_for_10m()
        effective_max = min(provider_max, scale_max)
        if delta > 0:
            new_zoom = min(self._zoom + 1, effective_max)
        else:
            new_zoom = max(self._zoom - 1, MIN_ZOOM)
        if new_zoom != self._zoom:
            # Compute lat/lon under cursor so we can keep it fixed after zoom
            pos = event.position()
            lat_at_cursor, lon_at_cursor = self.px_to_lat_lon(pos.x(), pos.y())
            self._zoom = new_zoom
            # Where does the same lat/lon appear in the new zoom?
            from bimap.engine.tile_math import lat_lon_to_pixel, pixel_to_lat_lon
            new_coord = lat_lon_to_pixel(
                lat_at_cursor, lon_at_cursor,
                self._center_lat, self._center_lon,
                new_zoom, self.width(), self.height()
            )
            # Shift the centre so the cursor lat/lon stays under the cursor
            shift_x = new_coord.px - pos.x()
            shift_y = new_coord.py - pos.y()
            new_lat, new_lon = pixel_to_lat_lon(
                self.width() / 2 + shift_x,
                self.height() / 2 + shift_y,
                self._center_lat, self._center_lon,
                new_zoom, self.width(), self.height()
            )
            self._center_lat = new_lat
            self._center_lon = new_lon
            # Do NOT clear self._tiles here — lower-zoom tiles already in cache
            # are needed by _scaled_fallback_tile when the server rejects high-zoom
            # requests (e.g. OSM returns HTTP 400 beyond zoom 19).
            # The 300-tile LRU eviction in _on_tile_ready manages memory instead.
            self._pending.clear()  # cancel any in-flight requests for the old zoom
            self._refresh_tiles()
            self.update()
            self.viewport_changed.emit(self._center_lat, self._center_lon, self._zoom)

    def zoom_in(self) -> None:
        """Zoom in one level, centred on the current viewport centre."""
        provider_max = TILE_PROVIDERS.get(self._tile_provider, {}).get("max_zoom", MAX_ZOOM)
        effective_max = min(provider_max, self._max_zoom_for_10m())
        self.set_viewport(self._center_lat, self._center_lon,
                          min(self._zoom + 1, effective_max))

    def zoom_out(self) -> None:
        """Zoom out one level, centred on the current viewport centre."""
        self.set_viewport(self._center_lat, self._center_lon,
                          max(self._zoom - 1, MIN_ZOOM))

    def _max_zoom_for_10m(self, min_viewport_m: float = 10.0) -> int:
        """Return the highest zoom level at which the viewport width stays >= min_viewport_m.

        Prevents zooming so close that map geometry distorts below 10 m resolution.
        Tiles: at zoom z, metres/pixel at latitude φ = cos(φ) × 40075016 / (256 × 2^z).
        Viewport width in metres = width_px × metres_per_pixel.
        Solving for z: z_max = floor(log2(cos(φ) × 40075016 × w / (256 × min_m))).
        """
        w = self.width()
        if w <= 0:
            # Widget not yet laid out — allow any zoom
            return MAX_ZOOM
        cos_lat = math.cos(math.radians(self._center_lat))
        numerator = cos_lat * 40_075_016.0 * w
        denominator = 256.0 * min_viewport_m
        if numerator <= 0 or denominator <= 0:
            return MAX_ZOOM
        z_max = int(math.floor(math.log2(numerator / denominator)))
        return max(MIN_ZOOM, min(MAX_ZOOM, z_max))

    def select_element(self, element_type: str, element_id: str) -> None:
        """Highlight a specific element on the canvas (pass to interaction handler)."""
        if hasattr(self._interaction, 'set_selected'):
            self._interaction.set_selected(element_type, element_id)
        self.update()

    def _hit_test(self, px: float, py: float) -> tuple[str, str]:
        """Return (element_type, element_id) of the topmost element at canvas pixel."""
        if not self._project:
            return "", ""
        import math as _math
        point = QPointF(px, py)
        # Annotations are rendered above the other map elements.
        for ann in reversed(self._project.annotations):
            if ann.visible and self._interaction._point_in_annotation(point, ann, self):
                return "annotation", str(ann.id)
        # Keypoints first (small click target)
        for kp in self._project.keypoints:
            kp_px = self.lat_lon_to_px(kp.lat, kp.lon)
            dx = kp_px.x() - px
            dy = kp_px.y() - py
            if _math.sqrt(dx * dx + dy * dy) <= kp.icon_size + 4:
                return "keypoint", str(kp.id)
        # Then zones
        lat, lon = self.px_to_lat_lon(px, py)
        for zone in self._project.zones:
            if self._interaction._point_in_zone(lat, lon, zone, self):
                return "zone", str(zone.id)
        return "", ""

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        pos = event.pos()
        # In MEASURE mode the only context action is to clear the measurement
        if self._interaction.tool == ToolMode.MEASURE:
            menu = QMenu(self)
            act_clear = menu.addAction(t("Clear Measurement"))
            if menu.exec(event.globalPos()) == act_clear:
                handler = self._interaction
                handler._measure_pts.clear()
                handler._measure_latlon.clear()
                handler.request_repaint.emit()
            return
        hit_type, hit_id = self._hit_test(float(pos.x()), float(pos.y()))
        menu = QMenu(self)
        if not hit_type:
            # Empty canvas — offer text annotation creation at this position
            act_text = menu.addAction(t("📝  Add Text here"))
            chosen = menu.exec(event.globalPos())
            lat, lon = self.px_to_lat_lon(float(pos.x()), float(pos.y()))
            if chosen == act_text:
                self.add_annotation_requested.emit("text_box", lat, lon)
            return
        # Check if this element has an extension defined
        element = None
        if self._project:
            element = next(
                (e for e in (*self._project.zones, *self._project.keypoints)
                 if str(getattr(e, "id", "")) == hit_id),
                None
            )
        has_extension = bool(element and getattr(element, "extension_html", ""))
        # Check if there are applicable form designs for this element type
        has_forms = False
        if self._project and hasattr(self._project, "form_designs"):
            has_forms = any(
                fd.target in ("both", hit_type)
                for fd in self._project.form_designs
            )
        act_edit     = menu.addAction(t("✏  Edit…"))
        act_move     = menu.addAction(t("↔  Move"))
        if has_forms:
            act_edit_info = menu.addAction(t("📝  Edit Info…"))
        else:
            act_edit_info = None
        act_metadata = menu.addAction(t("📋  View Metadata…"))
        if has_extension:
            act_open_ext = menu.addAction(t("Open Data Viewer"))
        else:
            act_open_ext = None
        if hit_type == "keypoint":
            act_to_zone = menu.addAction(t("⬡  Convert to Zone by Color…"))
        else:
            act_to_zone = None
        menu.addSeparator()
        act_remove   = menu.addAction(t("🗑  Remove…"))
        chosen = menu.exec(event.globalPos())
        if chosen == act_remove:
            self.context_action_requested.emit("remove", hit_type, hit_id)
        elif chosen == act_edit:
            self.context_action_requested.emit("edit", hit_type, hit_id)
        elif chosen == act_move:
            self.context_action_requested.emit("move", hit_type, hit_id)
        elif act_edit_info and chosen == act_edit_info:
            self.context_action_requested.emit("edit_info", hit_type, hit_id)
        elif chosen == act_metadata:
            self.context_action_requested.emit("view_metadata", hit_type, hit_id)
        elif act_open_ext and chosen == act_open_ext:
            self.context_action_requested.emit("open_extension", hit_type, hit_id)
        elif act_to_zone and chosen == act_to_zone:
            self._convert_keypoint_to_zone(hit_id)

    def _convert_keypoint_to_zone(self, keypoint_id: str) -> None:
        """Flood-fill the map tiles from the keypoint pixel and create a polygon zone."""
        if not self._project:
            return
        kp = next((k for k in self._project.keypoints if str(k.id) == keypoint_id), None)
        if kp is None:
            return

        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QSlider, QDialogButtonBox
        from collections import deque

        # ── Ask user for tolerance ────────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle(t("Convert to Zone by Color"))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(t("Color tolerance (0 = exact match, 100 = all colors):")))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(30)
        lay.addWidget(slider)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if not dlg.exec():
            return
        tolerance = slider.value()

        # ── Render tiles-only into a QImage ──────────────────────────────────
        img = QImage(self.width(), self.height(), QImage.Format.Format_RGB32)
        img.fill(QColor(220, 220, 220))
        img_painter = QPainter(img)
        self._paint_tiles(img_painter)
        img_painter.end()

        # ── Find seed pixel ────────────────────────────────────────────────
        seed_pt = self.lat_lon_to_px(kp.lat, kp.lon)
        sx, sy = int(round(seed_pt.x())), int(round(seed_pt.y()))
        w, h = self.width(), self.height()
        if not (0 <= sx < w and 0 <= sy < h):
            return

        seed_rgb = img.pixel(sx, sy)
        seed_r = (seed_rgb >> 16) & 0xFF
        seed_g = (seed_rgb >> 8) & 0xFF
        seed_b = seed_rgb & 0xFF

        def _in_tolerance(px_rgb: int) -> bool:
            r = (px_rgb >> 16) & 0xFF
            g = (px_rgb >> 8) & 0xFF
            b = px_rgb & 0xFF
            return (abs(r - seed_r) + abs(g - seed_g) + abs(b - seed_b)) <= tolerance * 3

        # ── BFS flood fill (limit area to avoid runaway on uniform tiles) ────
        MAX_PIXELS = 200_000
        filled: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int]] = deque()
        queue.append((sx, sy))
        filled.add((sx, sy))
        while queue and len(filled) < MAX_PIXELS:
            cx, cy = queue.popleft()
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in filled:
                    if _in_tolerance(img.pixel(nx, ny)):
                        filled.add((nx, ny))
                        queue.append((nx, ny))

        if len(filled) < 4:
            return

        # ── Extract boundary pixels (pixels in `filled` adjacent to outside) ─
        boundary = [
            (x, y) for x, y in filled
            if any(
                (x + dx, y + dy) not in filled
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
        ]

        # ── Simplify: convex hull via gift-wrapping ──────────────────────────
        if len(boundary) < 3:
            return

        def _cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        pts = sorted(set(boundary))
        n = len(pts)
        lower: list[tuple[int, int]] = []
        for p in pts:
            while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        upper: list[tuple[int, int]] = []
        for p in reversed(pts):
            while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        hull = lower[:-1] + upper[:-1]

        # Subsample hull to at most 64 vertices to keep zones manageable
        step = max(1, len(hull) // 64)
        hull = hull[::step]

        # ── Convert pixel hull to lat/lon coords ─────────────────────────────
        from bimap.models.zone import LatLon, Zone, ZoneType
        coords = [LatLon(lat=ll[0], lon=ll[1])
                  for ll in (self.px_to_lat_lon(float(x), float(y)) for x, y in hull)]
        if len(coords) < 3:
            return
        zone = Zone(zone_type=ZoneType.POLYGON, coordinates=coords, name=f"{kp.info_card.title} Zone")
        zone.label.text = zone.name
        self.draw_finished.emit("zone", zone)

    def keyPressEvent(self, event) -> None:
        self._interaction.key_press(event, self)

    def closeEvent(self, event) -> None:
        """Clean up tile pixmaps before the widget is destroyed."""
        self._tiles.clear()
        self._pending.clear()
        self._thread_pool.waitForDone(2000)
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_tiles()
