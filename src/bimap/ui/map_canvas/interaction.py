"""
Interaction handler — translates mouse/keyboard events into map actions.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from PyQt6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPolygonF,
)
from PyQt6.QtWidgets import QToolTip

from bimap.i18n import t
from bimap.models.annotation import Annotation, AnnotationType, AnnotationStyle, CanvasPosition
from bimap.models.keypoint import InfoCard, Keypoint
from bimap.models.zone import LatLon, Zone, ZoneType

if TYPE_CHECKING:
    from bimap.ui.map_canvas.tile_widget import TileWidget


class ToolMode(StrEnum):
    SELECT = "select"
    PAN = "pan"
    DRAW_POLYGON = "draw_polygon"
    DRAW_RECTANGLE = "draw_rectangle"
    DRAW_CIRCLE = "draw_circle"
    DRAW_KEYPOINT = "draw_keypoint"
    DRAW_TEXT = "draw_text"
    MAGIC_WAND = "magic_wand"
    MOVE_ELEMENT = "move_element"
    ROTATE_ELEMENT = "rotate_element"
    MEASURE = "measure"
    DIMENSION = "dimension"


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two lat/lon points (Haversine)."""
    R = 6_371_000.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(1.0, a)))


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing in degrees (0–360, 0=N, 90=E) from point 1 to point 2."""
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    x = math.sin(Δλ) * math.cos(φ2)
    y = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(Δλ)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _bearing_label(deg: float) -> str:
    """Return a compact bearing string like '045° NE'."""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = round(deg / 45) % 8
    return f"{deg:.0f}° {dirs[idx]}"


def _format_distance_m(distance: float) -> str:
    """Format local dimensions in metres and larger dimensions in kilometres."""
    if distance < 1000:
        return f"{distance:.0f} m"
    if distance < 10_000:
        return f"{distance / 1000:.2f} km"
    return f"{distance / 1000:.1f} km"


def _spherical_area_m2(latlon: list[tuple[float, float]]) -> float:
    """Approximate polygon area in m² using the spherical excess formula."""
    if len(latlon) < 3:
        return 0.0
    R = 6_371_000.0
    n = len(latlon)
    total = 0.0
    for i in range(n):
        lat1, lon1 = latlon[i]
        lat2, lon2 = latlon[(i + 1) % n]
        total += math.radians(lon2 - lon1) * (2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(total) * R * R / 2.0


class InteractionHandler(QObject):
    """Manages drawing state and emits signals when elements are created."""

    request_repaint = pyqtSignal()
    draw_finished = pyqtSignal(str, object)           # element_type, model_object
    element_selected = pyqtSignal(str, str)           # element_type, id string
    multi_select_finished = pyqtSignal(list)          # list[(etype, eid)]
    element_move_dropped = pyqtSignal(str, str, float, float)  # etype, eid, lat, lon
    open_extension_requested = pyqtSignal(str, str)   # element_type, element_id
    element_rotated = pyqtSignal(str, str, float)     # etype, eid, new_degrees

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tool: ToolMode = ToolMode.PAN
        # In-progress polygon vertices (canvas-pixel QPointF list)
        self._polygon_pts: list[QPointF] = []
        # Rectangle drag state
        self._rect_start: QPointF | None = None
        self._rect_end: QPointF | None = None
        # Circle drag state
        self._circle_center: QPointF | None = None
        self._circle_edge: QPointF | None = None
        # Current mouse position
        self._mouse_pos: QPointF = QPointF(0, 0)
        # Currently selected element
        self._selected_type: str | None = None
        self._selected_id: str | None = None
        # Magic-wand lasso state
        self._lasso_pts: list[QPointF] = []
        self._lasso_active: bool = False
        self._multi_selected: list[tuple[str, str]] = []
        self._lasso_zone: "Zone | None" = None  # polygon built from last lasso
        # Move-element state
        self._move_element_type: str | None = None
        self._move_element_id: str | None = None
        self._move_dragging = False
        # Precision-move preview pixel (set by arrow-key nudge, cleared on mouse move)
        self._move_preview_px: QPointF | None = None
        # Rotate-element state
        self._rotate_element_type: str | None = None
        self._rotate_element_id: str | None = None
        self._rotate_center_latlon: tuple[float, float] | None = None
        self._rotate_current_deg: float = 0.0
        # Drag-to-rotate tracking
        self._rotate_dragging: bool = False
        self._rotate_drag_start_angle: float = 0.0  # angle of mouse at drag start (degrees)
        self._rotate_drag_start_deg: float = 0.0    # element angle at drag start
        # Measurement tool state
        self._measure_pts: list[QPointF] = []
        self._measure_latlon: list[tuple[float, float]] = []
        # Hover tooltip state
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._on_hover_timeout)
        self._hover_pos: QPointF | None = None
        self._hover_canvas: "TileWidget | None" = None

    @property
    def tool(self) -> ToolMode:
        return self._tool

    @property
    def selected_type(self) -> str | None:
        return self._selected_type

    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    def set_selected(self, element_type: str, element_id: str) -> None:
        """Programmatically select an element and request a repaint."""
        self._selected_type = element_type
        self._selected_id = element_id
        self.request_repaint.emit()

    def set_tool(self, mode: ToolMode) -> None:
        self._tool = mode
        self._reset_draw_state()

    @property
    def multi_selected(self) -> list[tuple[str, str]]:
        return self._multi_selected

    def _reset_draw_state(self) -> None:
        self._polygon_pts.clear()
        self._rect_start = None
        self._rect_end = None
        self._circle_center = None
        self._circle_edge = None
        self._lasso_pts.clear()
        self._lasso_active = False
        self._multi_selected.clear()
        self._lasso_zone = None
        self._move_element_type = None
        self._move_element_id = None
        self._move_dragging = False
        self._move_preview_px = None
        self._rotate_element_type = None
        self._rotate_element_id = None
        self._rotate_center_latlon = None
        self._rotate_current_deg = 0.0
        self._rotate_dragging = False
        self._measure_pts.clear()
        self._measure_latlon.clear()
        self.request_repaint.emit()

    # ── Mouse events ───────────────────────────────────────────────────────────

    def mouse_press(self, event: QMouseEvent, canvas: "TileWidget") -> None:
        pos = event.position()
        btn = event.button()
        if btn != Qt.MouseButton.LeftButton:
            return

        match self._tool:
            case ToolMode.DRAW_POLYGON:
                self._polygon_pts.append(QPointF(pos))
                self.request_repaint.emit()

            case ToolMode.DRAW_RECTANGLE:
                self._rect_start = QPointF(pos)
                self._rect_end = QPointF(pos)

            case ToolMode.DRAW_CIRCLE:
                self._circle_center = QPointF(pos)
                self._circle_edge = QPointF(pos)

            case ToolMode.DRAW_KEYPOINT:
                lat, lon = canvas.px_to_lat_lon(pos.x(), pos.y())
                kp = Keypoint(lat=lat, lon=lon)
                kp.info_card.title = "New Point"
                self.draw_finished.emit("keypoint", kp)

            case ToolMode.DRAW_TEXT:
                lat, lon = canvas.px_to_lat_lon(pos.x(), pos.y())
                ann = Annotation(
                    ann_type=AnnotationType.TEXT_BOX,
                    anchor_lat=lat,
                    anchor_lon=lon,
                    content="Text",
                )
                ann.position = CanvasPosition(x=pos.x(), y=pos.y(), width=120, height=40)
                self.draw_finished.emit("annotation", ann)

            case ToolMode.SELECT:
                self._try_select(pos, canvas)

            case ToolMode.MAGIC_WAND:
                self._lasso_pts = [QPointF(pos)]
                self._lasso_active = True
                self._multi_selected.clear()

            case ToolMode.MEASURE:
                lat, lon = canvas.px_to_lat_lon(pos.x(), pos.y())
                self._measure_pts.append(QPointF(pos))
                self._measure_latlon.append((lat, lon))
                self.request_repaint.emit()

            case ToolMode.DIMENSION:
                lat, lon = canvas.px_to_lat_lon(pos.x(), pos.y())
                self._measure_pts.append(QPointF(pos))
                self._measure_latlon.append((lat, lon))
                if len(self._measure_latlon) == 2:
                    (start_lat, start_lon), (end_lat, end_lon) = self._measure_latlon
                    distance = _haversine_m(start_lat, start_lon, end_lat, end_lon)
                    distance_text = _format_distance_m(distance)
                    ann = Annotation(
                        ann_type=AnnotationType.DIMENSION,
                        content=distance_text,
                        dimension_start_lat=start_lat,
                        dimension_start_lon=start_lon,
                        dimension_end_lat=end_lat,
                        dimension_end_lon=end_lon,
                    )
                    ann.style.background_alpha = 0
                    self.draw_finished.emit("annotation", ann)
                    self._measure_pts.clear()
                    self._measure_latlon.clear()
                self.request_repaint.emit()

            case ToolMode.MOVE_ELEMENT:
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    # Ctrl-click picks an element and starts a drag in one gesture.
                    if not self._move_element_type:
                        self._pick_element_for_move(pos, canvas)
                    if self._move_element_type:
                        self._move_dragging = True
                        self._mouse_pos = QPointF(pos)
                        self.request_repaint.emit()
                elif self._move_element_type:
                    self._drop_moved_element(pos, canvas)
                else:
                    # No element tracked yet — hit-test to pick one to move
                    self._pick_element_for_move(pos, canvas)

            case ToolMode.ROTATE_ELEMENT:
                self._pick_element_for_rotate(pos, canvas)
                # Begin drag immediately if element is now active and cursor is
                # not on the centre point (avoids accidental drag on first click).
                if self._rotate_element_type and self._rotate_center_latlon:
                    clat, clon = self._rotate_center_latlon
                    cx_pt = canvas.lat_lon_to_px(clat, clon)
                    if cx_pt:
                        dx = pos.x() - cx_pt.x()
                        dy = pos.y() - cx_pt.y()
                        if abs(dx) + abs(dy) > 6:
                            self._rotate_dragging = True
                            self._rotate_drag_start_deg = self._rotate_current_deg
                            self._rotate_drag_start_angle = math.degrees(math.atan2(dy, dx))

    def mouse_move(self, event: QMouseEvent, canvas: "TileWidget") -> None:
        self._mouse_pos = event.position()
        # Mouse movement cancels the arrow-key nudge offset
        self._move_preview_px = None
        match self._tool:
            case ToolMode.DRAW_RECTANGLE if self._rect_start:
                self._rect_end = QPointF(event.position())
                self.request_repaint.emit()
            case ToolMode.DRAW_CIRCLE if self._circle_center:
                self._circle_edge = QPointF(event.position())
                self.request_repaint.emit()
            case ToolMode.DRAW_POLYGON if self._polygon_pts:
                self.request_repaint.emit()
            case ToolMode.MAGIC_WAND if self._lasso_active:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    self._lasso_pts.append(QPointF(event.position()))
                self.request_repaint.emit()
            case ToolMode.MOVE_ELEMENT:
                self.request_repaint.emit()
            case ToolMode.ROTATE_ELEMENT if self._rotate_dragging and self._rotate_center_latlon:
                # Compute angle from zone centre to current cursor position and
                # use the delta from drag-start to update rotation continuously.
                clat, clon = self._rotate_center_latlon
                cx_pt = canvas.lat_lon_to_px(clat, clon)
                if cx_pt:
                    dx = event.position().x() - cx_pt.x()
                    dy = event.position().y() - cx_pt.y()
                    if abs(dx) + abs(dy) > 2:
                        current_angle = math.degrees(math.atan2(dy, dx))
                        delta = current_angle - self._rotate_drag_start_angle
                        self._rotate_current_deg = (self._rotate_drag_start_deg + delta) % 360.0
                        self.request_repaint.emit()
            case ToolMode.SELECT:
                # Trigger hover tooltip after a short delay
                self._hover_pos = QPointF(event.position())
                self._hover_canvas = canvas
                self._hover_timer.start(200)  # 200ms debounce

    def mouse_release(self, event: QMouseEvent, canvas: "TileWidget") -> None:
        pos = event.position()
        match self._tool:
            case ToolMode.DRAW_RECTANGLE if self._rect_start and self._rect_end:
                self._finish_rectangle(canvas)
            case ToolMode.DRAW_CIRCLE if self._circle_center and self._circle_edge:
                self._finish_circle(canvas)
            case ToolMode.MAGIC_WAND if self._lasso_active:
                self._lasso_active = False
                self._finish_lasso(canvas)
            case ToolMode.MOVE_ELEMENT if self._move_dragging:
                self._move_dragging = False
                self._drop_moved_element(pos, canvas)
            case ToolMode.ROTATE_ELEMENT if self._rotate_dragging:
                # Commit the final drag angle as a single undo command.
                self._rotate_dragging = False
                if self._rotate_element_type:
                    self.element_rotated.emit(
                        self._rotate_element_type,
                        self._rotate_element_id or "",
                        self._rotate_current_deg,
                    )

    def mouse_double_click(self, event: QMouseEvent, canvas: "TileWidget") -> None:
        if self._tool == ToolMode.DRAW_POLYGON and len(self._polygon_pts) >= 3:
            self._finish_polygon(canvas)
            return
        if self._tool == ToolMode.SELECT:
            pos = event.position()
            project = getattr(canvas, "_project", None)
            if project is None:
                return
            # Hit-test keypoints first, then zones
            lat, lon = canvas.px_to_lat_lon(pos.x(), pos.y())
            for kp in project.keypoints:
                px = canvas.lat_lon_to_px(kp.lat, kp.lon)
                if px and (pos - px).manhattanLength() <= 16:
                    if getattr(kp, "extension_html", ""):
                        self.open_extension_requested.emit("keypoint", str(kp.id))
                    return
            for zone in project.zones:
                if self._point_in_zone(lat, lon, zone, canvas):
                    if getattr(zone, "extension_html", ""):
                        self.open_extension_requested.emit("zone", str(zone.id))
                    return

    def key_press(self, event: QKeyEvent, canvas: "TileWidget") -> None:
        _NUDGE_PX = 8.0
        if event.key() == Qt.Key.Key_Escape:
            self._reset_draw_state()
            self.request_repaint.emit()
        elif event.key() == Qt.Key.Key_Return and self._tool == ToolMode.DRAW_POLYGON:
            if len(self._polygon_pts) >= 3:
                self._finish_polygon(canvas)
        elif self._tool == ToolMode.ROTATE_ELEMENT and self._rotate_element_type:
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Right):
                self._rotate_current_deg = (self._rotate_current_deg + 1.0) % 360.0
                self.element_rotated.emit(
                    self._rotate_element_type,
                    self._rotate_element_id or "",
                    self._rotate_current_deg,
                )
                self.request_repaint.emit()
            elif event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Left):
                self._rotate_current_deg = (self._rotate_current_deg - 1.0) % 360.0
                self.element_rotated.emit(
                    self._rotate_element_type,
                    self._rotate_element_id or "",
                    self._rotate_current_deg,
                )
                self.request_repaint.emit()
        elif self._tool == ToolMode.MOVE_ELEMENT and self._move_element_type:
            # Arrow-key nudge: shift the planned drop position by N pixels
            base = self._move_preview_px or self._mouse_pos
            if event.key() == Qt.Key.Key_Left:
                self._move_preview_px = QPointF(base.x() - _NUDGE_PX, base.y())
            elif event.key() == Qt.Key.Key_Right:
                self._move_preview_px = QPointF(base.x() + _NUDGE_PX, base.y())
            elif event.key() == Qt.Key.Key_Up:
                self._move_preview_px = QPointF(base.x(), base.y() - _NUDGE_PX)
            elif event.key() == Qt.Key.Key_Down:
                self._move_preview_px = QPointF(base.x(), base.y() + _NUDGE_PX)
            self.request_repaint.emit()

    def _on_hover_timeout(self) -> None:
        """Called after hover delay — hit-test data features and show tooltip."""
        if self._hover_pos is None or self._hover_canvas is None:
            return
        canvas = self._hover_canvas
        px, py = self._hover_pos.x(), self._hover_pos.y()
        
        # Hit-test data layers
        result = canvas.hit_test_data_layers(px, py)
        if result is None:
            return
        
        source_id, row_index = result
        
        # Fetch row data
        rows = canvas._data_layer_rows.get(source_id, [])
        if row_index < 0 or row_index >= len(rows):
            return
        row_data = dict(rows[row_index])
        
        # Build tooltip text: show first few non-internal attributes
        tooltip_parts = []
        for key, value in row_data.items():
            if key.startswith("_"):
                continue
            if len(tooltip_parts) >= 3:  # Limit to 3 attributes
                break
            tooltip_parts.append(f"{key}: {value}")
        
        if tooltip_parts:
            tooltip_text = "\n".join(tooltip_parts)
            # Show tooltip at global mouse position
            global_pos = canvas.mapToGlobal(self._hover_pos.toPoint())
            QToolTip.showText(global_pos, tooltip_text, canvas)

    # ── Finish drawing helpers ─────────────────────────────────────────────────

    def _finish_polygon(self, canvas: "TileWidget") -> None:
        coords = []
        for p in self._polygon_pts:
            lat, lon = canvas.px_to_lat_lon(p.x(), p.y())
            coords.append(LatLon(lat=lat, lon=lon))
        self._polygon_pts.clear()
        zone = Zone(zone_type=ZoneType.POLYGON, coordinates=coords, name=t("New Zone"))
        zone.label.text = zone.name
        self.draw_finished.emit("zone", zone)
        self.request_repaint.emit()

    def _finish_rectangle(self, canvas: "TileWidget") -> None:
        s, e = self._rect_start, self._rect_end
        corners = []
        for cx, cy in [(s.x(), s.y()), (e.x(), s.y()), (e.x(), e.y()), (s.x(), e.y())]:
            lat, lon = canvas.px_to_lat_lon(cx, cy)
            corners.append(LatLon(lat=lat, lon=lon))
        zone = Zone(zone_type=ZoneType.RECTANGLE, coordinates=corners, name=t("New Zone"))
        zone.label.text = zone.name
        self._rect_start = self._rect_end = None
        self.draw_finished.emit("zone", zone)
        self.request_repaint.emit()

    def _finish_circle(self, canvas: "TileWidget") -> None:
        c = self._circle_center
        e = self._circle_edge
        lat, lon = canvas.px_to_lat_lon(c.x(), c.y())
        dx = e.x() - c.x()
        dy = e.y() - c.y()
        radius_px = math.sqrt(dx * dx + dy * dy)
        from bimap.engine.tile_math import meters_per_pixel
        mpp = meters_per_pixel(lat, canvas.zoom)
        radius_m = radius_px * mpp
        zone = Zone(
            zone_type=ZoneType.CIRCLE,
            coordinates=[LatLon(lat=lat, lon=lon)],
            radius_m=max(1.0, radius_m),
            name=t("New Circle"),
        )
        zone.label.text = zone.name
        self._circle_center = self._circle_edge = None
        self.draw_finished.emit("zone", zone)
        self.request_repaint.emit()

    def _finish_lasso(self, canvas: "TileWidget") -> None:
        """Close the magic-wand lasso, multi-select enclosed elements, and build a polygon zone."""
        if len(self._lasso_pts) < 3 or not canvas._project:
            self._lasso_pts.clear()
            self._lasso_zone = None
            self.request_repaint.emit()
            return

        found: list[tuple[str, str]] = []
        project = canvas._project

        for zone in project.zones:
            if not zone.coordinates:
                continue
            if zone.zone_type == ZoneType.CIRCLE:
                c = zone.coordinates[0]
            else:
                c_lat = sum(p.lat for p in zone.coordinates) / len(zone.coordinates)
                c_lon = sum(p.lon for p in zone.coordinates) / len(zone.coordinates)

                class _P:
                    lat = c_lat
                    lon = c_lon
                c = _P()
            px = canvas.lat_lon_to_px(c.lat, c.lon)
            if self._point_in_lasso(px.x(), px.y()):
                found.append(("zone", str(zone.id)))

        for kp in project.keypoints:
            px = canvas.lat_lon_to_px(kp.lat, kp.lon)
            if self._point_in_lasso(px.x(), px.y()):
                found.append(("keypoint", str(kp.id)))

        # Build a polygon Zone from the lasso outline
        zone_coords = []
        for p in self._lasso_pts:
            lat, lon = canvas.px_to_lat_lon(p.x(), p.y())
            zone_coords.append(LatLon(lat=lat, lon=lon))
        lasso_zone = Zone(
            zone_type=ZoneType.POLYGON,
            coordinates=zone_coords,
            name="Zona Dinámica",
        )
        lasso_zone.label.text = lasso_zone.name

        # Auto-populate geo-space metadata attributes
        if zone_coords:
            c_lat = sum(c.lat for c in zone_coords) / len(zone_coords)
            c_lon = sum(c.lon for c in zone_coords) / len(zone_coords)
            # Approximate area via planar shoelace (degrees²) → convert to m²
            import math as _math
            n = len(zone_coords)
            area_deg2 = 0.0
            for i in range(n):
                j = (i + 1) % n
                area_deg2 += zone_coords[i].lat * zone_coords[j].lon
                area_deg2 -= zone_coords[j].lat * zone_coords[i].lon
            area_deg2 = abs(area_deg2) / 2.0
            # 1° lat ≈ 111_320 m; 1° lon ≈ 111_320 * cos(lat) m
            m_per_lat = 111_320.0
            m_per_lon = 111_320.0 * _math.cos(_math.radians(c_lat))
            area_m2 = area_deg2 * m_per_lat * m_per_lon
            # Approximate perimeter
            perim_m = 0.0
            for i in range(n):
                j = (i + 1) % n
                dlat = (zone_coords[j].lat - zone_coords[i].lat) * m_per_lat
                dlon = (zone_coords[j].lon - zone_coords[i].lon) * m_per_lon
                perim_m += _math.sqrt(dlat * dlat + dlon * dlon)
            import json as _json
            lasso_zone.metadata["lat"] = f"{c_lat:.6f}"
            lasso_zone.metadata["lon"] = f"{c_lon:.6f}"
            lasso_zone.metadata["area_m2"] = str(round(area_m2, 1))
            lasso_zone.metadata["perimeter_m"] = str(round(perim_m, 1))
            geo_coords = [
                {"lat": round(c.lat, 7), "lon": round(c.lon, 7)}
                for c in zone_coords
            ]
            lasso_zone.metadata["geo-space"] = _json.dumps(
                geo_coords, separators=(",", ":")
            )
            if "geo-space" not in lasso_zone.metadata_hidden:
                lasso_zone.metadata_hidden.append("geo-space")

        self._lasso_zone = lasso_zone

        self._multi_selected = found
        self._lasso_pts.clear()
        # Always emit so the handler can offer both delete and create-polygon
        self.multi_select_finished.emit(found)
        self.request_repaint.emit()

    def _point_in_lasso(self, x: float, y: float) -> bool:
        """Ray-casting point-in-polygon test against the lasso path."""
        pts = self._lasso_pts
        inside = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i].x(), pts[i].y()
            xj, yj = pts[j].x(), pts[j].y()
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            ):
                inside = not inside
            j = i
        return inside

    def start_move_element(self, element_type: str, element_id: str) -> None:
        """Enter move mode: next left-click will drop the element at that position."""
        self._move_element_type = element_type
        self._move_element_id = element_id
        self._tool = ToolMode.MOVE_ELEMENT
        self.request_repaint.emit()

    def move_preview_position(self, canvas: "TileWidget") -> tuple[float, float] | None:
        """Return the current snapped position for the element being moved."""
        if (
            not self._move_dragging
            or not self._move_element_type
            or not self._move_element_id
        ):
            return None
        raw = self._move_preview_px or self._mouse_pos
        magnet = self._snap_to_nearest_element_px(raw, canvas)
        pos = magnet if magnet is not None else self._snap_to_grid_px(raw, canvas)
        return canvas.px_to_lat_lon(pos.x(), pos.y())

    def _drop_moved_element(self, pos: QPointF, canvas: "TileWidget") -> None:
        """Commit the planned move using element and grid snapping."""
        if not self._move_element_type or not self._move_element_id:
            return
        drop_raw = self._move_preview_px or pos
        magnet = self._snap_to_nearest_element_px(drop_raw, canvas)
        drop_px = magnet if magnet is not None else self._snap_to_grid_px(drop_raw, canvas)
        lat, lon = canvas.px_to_lat_lon(drop_px.x(), drop_px.y())
        self.element_move_dropped.emit(self._move_element_type, self._move_element_id, lat, lon)
        self._move_element_type = None
        self._move_element_id = None
        self._move_preview_px = None
        # Keep MOVE_ELEMENT active so the user can move more elements
        self.request_repaint.emit()

    def _pick_element_for_move(self, pos: QPointF, canvas: "TileWidget") -> None:
        """Hit-test to pick an element so it can be moved on the next click."""
        if not canvas._project:
            return
        lat, lon = canvas.px_to_lat_lon(pos.x(), pos.y())
        for kp in canvas._project.keypoints:
            kp_px = canvas.lat_lon_to_px(kp.lat, kp.lon)
            dx = kp_px.x() - pos.x()
            dy = kp_px.y() - pos.y()
            if math.sqrt(dx * dx + dy * dy) <= kp.icon_size + 4:
                self._move_element_type = "keypoint"
                self._move_element_id = str(kp.id)
                self.request_repaint.emit()
                return
        for zone in canvas._project.zones:
            if getattr(zone, "locked", False):
                continue
            if self._point_in_zone(lat, lon, zone, canvas):
                self._move_element_type = "zone"
                self._move_element_id = str(zone.id)
                self.request_repaint.emit()
                return
        for ann in canvas._project.annotations:
            if ann.visible and self._point_in_annotation(pos, ann, canvas):
                self._move_element_type = "annotation"
                self._move_element_id = str(ann.id)
                self.request_repaint.emit()
                return

    # ── Selection ──────────────────────────────────────────────────────────────

    def _try_select(self, pos: QPointF, canvas: "TileWidget") -> None:
        if not canvas._project:
            return
        lat, lon = canvas.px_to_lat_lon(pos.x(), pos.y())

        # Check data layer features first (WFS/CSV/etc.)
        hit = canvas.hit_test_data_layers(pos.x(), pos.y())
        if hit:
            source_id, row_index = hit
            canvas.select_data_feature(source_id, row_index)
            return

        # Clear data feature selection if clicking elsewhere
        canvas.clear_data_feature_selection()

        # Annotations are painted above the other map elements.
        for ann in reversed(canvas._project.annotations):
            if ann.visible and self._point_in_annotation(pos, ann, canvas):
                self._selected_type = "annotation"
                self._selected_id = str(ann.id)
                self.element_selected.emit("annotation", str(ann.id))
                return

        # Check keypoints (small target)
        for kp in canvas._project.keypoints:
            kp_px = canvas.lat_lon_to_px(kp.lat, kp.lon)
            dx = kp_px.x() - pos.x()
            dy = kp_px.y() - pos.y()
            if math.sqrt(dx * dx + dy * dy) <= kp.icon_size + 4:
                self._selected_type = "keypoint"
                self._selected_id = str(kp.id)
                self.element_selected.emit("keypoint", str(kp.id))
                return

        # Check zones (skip locked zones)
        for zone in canvas._project.zones:
            if getattr(zone, 'locked', False):
                continue
            if self._point_in_zone(lat, lon, zone, canvas):
                self._selected_type = "zone"
                self._selected_id = str(zone.id)
                self.element_selected.emit("zone", str(zone.id))
                return

        self._selected_type = None
        self._selected_id = None
        self.element_selected.emit("", "")

    def _point_in_annotation(
        self, pos: QPointF, ann: Annotation, canvas: "TileWidget"
    ) -> bool:
        """Return whether a canvas point is close enough to an annotation."""
        if ann.ann_type == AnnotationType.DIMENSION:
            coords = (
                ann.dimension_start_lat, ann.dimension_start_lon,
                ann.dimension_end_lat, ann.dimension_end_lon,
            )
            if any(value is None for value in coords):
                return False
            start = canvas.lat_lon_to_px(ann.dimension_start_lat, ann.dimension_start_lon)
            end = canvas.lat_lon_to_px(ann.dimension_end_lat, ann.dimension_end_lon)
            dx, dy = end.x() - start.x(), end.y() - start.y()
            length_sq = dx * dx + dy * dy
            if length_sq == 0:
                return math.hypot(pos.x() - start.x(), pos.y() - start.y()) <= 8
            length = math.sqrt(length_sq)
            normal_x, normal_y = -dy / length, dx / length
            dimension_start = QPointF(start.x() + normal_x * 10, start.y() + normal_y * 10)
            dimension_end = QPointF(end.x() + normal_x * 10, end.y() + normal_y * 10)
            dim_dx = dimension_end.x() - dimension_start.x()
            dim_dy = dimension_end.y() - dimension_start.y()
            t = max(0.0, min(1.0, ((pos.x() - dimension_start.x()) * dim_dx + (pos.y() - dimension_start.y()) * dim_dy) / length_sq))
            nearest_x = dimension_start.x() + t * dim_dx
            nearest_y = dimension_start.y() + t * dim_dy
            if math.hypot(pos.x() - nearest_x, pos.y() - nearest_y) <= 10:
                return True
            font = QFont(ann.style.font_family, ann.style.font_size)
            metrics = QFontMetricsF(font)
            label_width = metrics.horizontalAdvance(ann.content)
            label_rect = QRectF(
                (dimension_start.x() + dimension_end.x()) / 2 - label_width / 2 - 3,
                (dimension_start.y() + dimension_end.y()) / 2 - metrics.ascent() - 4,
                label_width + 6,
                metrics.height(),
            )
            return label_rect.contains(pos)

        if ann.anchor_lat is not None and ann.anchor_lon is not None:
            origin = canvas.lat_lon_to_px(ann.anchor_lat, ann.anchor_lon)
            x, y = origin.x(), origin.y()
        else:
            x, y = ann.position.x, ann.position.y
        font = QFont(ann.style.font_family, ann.style.font_size)
        metrics = QFontMetricsF(font)
        lines = ann.content.split("\n")
        width = max((metrics.horizontalAdvance(line) for line in lines), default=40)
        height = metrics.height() * len(lines)
        padding = ann.style.padding
        rect = QRectF(x, y, width + padding * 2, height + padding * 2)
        if rect.contains(pos):
            return True
        if ann.ann_type == AnnotationType.CALLOUT and ann.target_lat is not None and ann.target_lon is not None:
            target = canvas.lat_lon_to_px(ann.target_lat, ann.target_lon)
            start = QPointF(x, y + height + padding)
            line_dx, line_dy = target.x() - start.x(), target.y() - start.y()
            line_sq = line_dx * line_dx + line_dy * line_dy
            if line_sq:
                ratio = max(0.0, min(1.0, ((pos.x() - start.x()) * line_dx + (pos.y() - start.y()) * line_dy) / line_sq))
                nearest = QPointF(start.x() + ratio * line_dx, start.y() + ratio * line_dy)
                return math.hypot(pos.x() - nearest.x(), pos.y() - nearest.y()) <= 8
        return False

    def _point_in_zone(self, lat: float, lon: float, zone: "Zone", canvas: "TileWidget") -> bool:
        """Simple polygon point-in-polygon test using canvas pixels."""
        if not zone.coordinates:
            return False
        if zone.zone_type == ZoneType.CIRCLE and zone.coordinates:
            c = zone.coordinates[0]
            from bimap.engine.tile_math import meters_per_pixel, lat_lon_to_tile_float
            import math as _math
            dlat = (lat - c.lat) * 111_320
            dlon = (lon - c.lon) * 111_320 * _math.cos(_math.radians(c.lat))
            dist = _math.sqrt(dlat * dlat + dlon * dlon)
            return dist <= zone.radius_m

        # Ray-casting for polygons
        pts = zone.coordinates
        inside = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i].lat, pts[i].lon
            xj, yj = pts[j].lat, pts[j].lon
            if ((yi > lon) != (yj > lon)) and (lat < (xj - xi) * (lon - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    # ── Preview painting ───────────────────────────────────────────────────────

    def paint_preview(self, painter: QPainter, canvas: "TileWidget") -> None:
        """Draw in-progress shape preview on the canvas painter."""
        match self._tool:
            case ToolMode.DRAW_POLYGON if self._polygon_pts:
                self._preview_polygon(painter)
            case ToolMode.DRAW_RECTANGLE if self._rect_start and self._rect_end:
                self._preview_rectangle(painter)
            case ToolMode.DRAW_CIRCLE if self._circle_center and self._circle_edge:
                self._preview_circle(painter)
            case ToolMode.MAGIC_WAND if len(self._lasso_pts) >= 2:
                self._preview_lasso(painter)
            case ToolMode.MOVE_ELEMENT if self._move_element_type:
                self._preview_move_crosshair(painter, canvas)
            case ToolMode.ROTATE_ELEMENT if self._rotate_element_type and self._rotate_center_latlon:
                self._preview_rotate_visor(painter, canvas)
            case ToolMode.MEASURE:
                self._preview_measurement(painter, canvas)
            case ToolMode.DIMENSION:
                self._preview_dimension(painter, canvas)

    def _preview_dimension(self, painter: QPainter, canvas: "TileWidget") -> None:
        """Show the dimension line before the second point is placed."""
        if not self._measure_latlon:
            return
        start = canvas.lat_lon_to_px(*self._measure_latlon[0])
        end = self._mouse_pos
        painter.setPen(QPen(QColor(255, 140, 0), 2, Qt.PenStyle.DashLine))
        painter.drawLine(start, end)
        painter.setBrush(QColor(255, 140, 0))
        painter.drawEllipse(start, 4.0, 4.0)
        painter.drawEllipse(end, 4.0, 4.0)

    def _preview_polygon(self, painter: QPainter) -> None:
        pts = self._polygon_pts + [self._mouse_pos]
        pen = QPen(QColor(51, 136, 255), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for i in range(1, len(pts)):
            painter.drawLine(pts[i - 1], pts[i])
        # Vertex dots
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(QPen(QColor(51, 136, 255), 1))
        for pt in self._polygon_pts:
            painter.drawEllipse(pt, 4.0, 4.0)

    def _preview_rectangle(self, painter: QPainter) -> None:
        s, e = self._rect_start, self._rect_end
        rect = QRectF(
            min(s.x(), e.x()), min(s.y(), e.y()),
            abs(e.x() - s.x()), abs(e.y() - s.y())
        )
        pen = QPen(QColor(51, 136, 255), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        fill = QColor(51, 136, 255, 40)
        painter.setBrush(fill)
        painter.drawRect(rect)

    def _preview_circle(self, painter: QPainter) -> None:
        c, e = self._circle_center, self._circle_edge
        dx = e.x() - c.x()
        dy = e.y() - c.y()
        r = math.sqrt(dx * dx + dy * dy)
        pen = QPen(QColor(51, 136, 255), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        fill = QColor(51, 136, 255, 40)
        painter.setBrush(fill)
        painter.drawEllipse(QRectF(c.x() - r, c.y() - r, r * 2, r * 2))

    def _preview_lasso(self, painter: QPainter) -> None:
        pen = QPen(QColor(255, 140, 0), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 140, 0, 30))
        painter.drawPolygon(QPolygonF(self._lasso_pts))

    def _preview_move_crosshair(self, painter: QPainter, canvas: "TileWidget") -> None:
        raw = self._move_preview_px or self._mouse_pos
        magnet = self._snap_to_nearest_element_px(raw, canvas)
        if magnet is not None:
            pos = magnet
            is_magnet = True
        else:
            pos = self._snap_to_grid_px(raw, canvas)
            is_magnet = False
        x, y = pos.x(), pos.y()
        if is_magnet:
            color = QColor(255, 120, 0)   # orange for magnet
        else:
            color = QColor(0, 200, 100)   # green for normal/grid
        pen = QPen(color, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(x - 12, y), QPointF(x + 12, y))
        painter.drawLine(QPointF(x, y - 12), QPointF(x, y + 12))
        painter.drawEllipse(QRectF(x - 7, y - 7, 14, 14))
        if is_magnet:
            # Draw extra magnet ring
            painter.setPen(QPen(color, 1, Qt.PenStyle.DashLine))
            painter.drawEllipse(QRectF(x - 14, y - 14, 28, 28))
        # Show nudge/grid/magnet hint
        snapped_grid = getattr(canvas, "_show_grid", False) and not is_magnet
        painter.setPen(color)
        font = QFont("Consolas", 9)
        painter.setFont(font)
        if is_magnet:
            hint = "🧲 magnet  ·  click to drop"
        elif snapped_grid and self._move_preview_px is not None:
            hint = "snap+nudge  ·  click to drop"
        elif snapped_grid:
            hint = "⬡ grid snap  ·  click to drop"
        else:
            hint = "↑↓←→ nudge  ·  click to drop"
        painter.drawText(QPointF(x + 14, y - 4), hint)

    def _pick_element_for_rotate(self, pos: QPointF, canvas: "TileWidget") -> None:
        """Select a zone under the cursor for rotation."""
        if not canvas._project:
            return
        lat, lon = canvas.px_to_lat_lon(pos.x(), pos.y())
        for zone in canvas._project.zones:
            if getattr(zone, "locked", False):
                continue
            if self._point_in_zone(lat, lon, zone, canvas):
                self._rotate_element_type = "zone"
                self._rotate_element_id = str(zone.id)
                coords = zone.coordinates
                if coords:
                    c_lat = sum(c.lat for c in coords) / len(coords)
                    c_lon = sum(c.lon for c in coords) / len(coords)
                else:
                    c_lat, c_lon = lat, lon
                self._rotate_center_latlon = (c_lat, c_lon)
                self._rotate_current_deg = getattr(zone, "rotation_deg", 0.0)
                self.element_selected.emit("zone", str(zone.id))
                self.request_repaint.emit()
                return

    def _preview_rotate_visor(self, painter: QPainter, canvas: "TileWidget") -> None:
        """Draw a angle-visor arc overlay centred on the zone being rotated."""
        if not self._rotate_center_latlon:
            return
        clat, clon = self._rotate_center_latlon
        cx_pt = canvas.lat_lon_to_px(clat, clon)
        if cx_pt is None:
            return
        cx, cy = cx_pt.x(), cx_pt.y()
        R = 52.0
        deg = self._rotate_current_deg

        # Outer reference ring (dark gray)
        pen_ring = QPen(QColor(90, 90, 90, 200), 1)
        painter.setPen(pen_ring)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(cx - R, cy - R, R * 2, R * 2))

        # 0° reference tick (east)
        painter.setPen(QPen(QColor(120, 120, 120, 140), 1))
        painter.drawLine(QPointF(cx, cy), QPointF(cx + R, cy))

        # Current angle arm (medium gray)
        rad = math.radians(deg)
        tx = cx + R * math.cos(rad)
        ty = cy + R * math.sin(rad)
        painter.setPen(QPen(QColor(160, 160, 160), 2))
        painter.drawLine(QPointF(cx, cy), QPointF(tx, ty))

        # Filled arc from 0 to current angle (dark gray transparent)
        from PyQt6.QtCore import QRectF as _QRF
        arc_rect = _QRF(cx - R * 0.55, cy - R * 0.55, R * 1.1, R * 1.1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(100, 100, 100, 50))
        painter.drawPie(arc_rect, 0, int(-deg * 16))  # Qt angles: 1/16th degree units

        # Degree label beside the arm
        font = QFont("Consolas", 10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(200, 200, 200))
        painter.drawText(QPointF(tx + 6, ty + 4), f"{deg:.1f}°")

        # Hint text
        painter.setPen(QColor(160, 160, 160, 180))
        font2 = QFont("Consolas", 8)
        painter.setFont(font2)
        hint = "🖥 drag to rotate  ·  ↑/→ +1°  ·  ↓/← −1°  ·  Esc to exit"
        if self._rotate_dragging:
            hint = f"🖥 dragging…  {self._rotate_current_deg:.1f}°  ·  release to commit"
        painter.drawText(QPointF(cx - R, cy + R + 14), hint)

    # ── Element magnet snap ────────────────────────────────────────────────────

    def _snap_to_nearest_element_px(
        self, pos: QPointF, canvas: "TileWidget", thresh_px: float = 20.0
    ) -> QPointF | None:
        """Return the pixel position of the nearest snap target within *thresh_px*.

        Snap targets are keypoints and zone centroids, excluding the element
        currently being moved (to avoid self-snap).
        """
        if not canvas._project:
            return None
        best_dist = thresh_px
        best_px: QPointF | None = None

        for kp in canvas._project.keypoints:
            # Skip self
            if self._move_element_type == "keypoint" and str(kp.id) == self._move_element_id:
                continue
            kp_px = canvas.lat_lon_to_px(kp.lat, kp.lon)
            if kp_px is None:
                continue
            d = math.sqrt((kp_px.x() - pos.x()) ** 2 + (kp_px.y() - pos.y()) ** 2)
            if d < best_dist:
                best_dist = d
                best_px = kp_px

        for zone in canvas._project.zones:
            if not zone.coordinates:
                continue
            if self._move_element_type == "zone" and str(zone.id) == self._move_element_id:
                continue
            pxs = [canvas.lat_lon_to_px(c.lat, c.lon) for c in zone.coordinates]
            pxs = [p for p in pxs if p is not None]
            if not pxs:
                continue
            cx = sum(p.x() for p in pxs) / len(pxs)
            cy = sum(p.y() for p in pxs) / len(pxs)
            centroid = QPointF(cx, cy)
            d = math.sqrt((cx - pos.x()) ** 2 + (cy - pos.y()) ** 2)
            if d < best_dist:
                best_dist = d
                best_px = centroid
            # Also snap to zone vertices
            for vp in pxs:
                d = math.sqrt((vp.x() - pos.x()) ** 2 + (vp.y() - pos.y()) ** 2)
                if d < best_dist:
                    best_dist = d
                    best_px = vp

        return best_px

    # ── Grid snap ──────────────────────────────────────────────────────────────

    def _snap_to_grid_px(self, pos: QPointF, canvas: "TileWidget") -> QPointF:
        """Snap a canvas-pixel position to the nearest grid intersection when grid is on."""
        if not getattr(canvas, "_show_grid", False):
            return pos
        from bimap.engine.tile_math import meters_per_pixel
        w = canvas.width()
        mpp = meters_per_pixel(canvas._center_lat, canvas._zoom)
        spacing_m = 500_000
        for s in (10, 25, 50, 100, 250, 500, 1000, 2500, 5000,
                  10000, 25000, 50000, 100000, 250000, 500000):
            if w / (s / mpp) < 25:
                spacing_m = s
                break
        spacing_lat = spacing_m / 111_320.0
        spacing_lon = spacing_m / (111_320.0 * math.cos(math.radians(canvas._center_lat)) + 1e-9)
        lat, lon = canvas.px_to_lat_lon(pos.x(), pos.y())
        snapped_lat = round(lat / spacing_lat) * spacing_lat
        snapped_lon = round(lon / spacing_lon) * spacing_lon
        snapped_px = canvas.lat_lon_to_px(snapped_lat, snapped_lon)
        return snapped_px if snapped_px else pos

    # ── Measurement preview ────────────────────────────────────────────────────

    def _preview_measurement(self, painter: QPainter, canvas: "TileWidget") -> None:
        """Draw the in-progress measurement path with segment distances."""
        # Show a simple crosshair when no points have been placed yet
        x, y = self._mouse_pos.x(), self._mouse_pos.y()
        if not self._measure_latlon:
            pen = QPen(QColor(255, 140, 0), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(x - 10, y), QPointF(x + 10, y))
            painter.drawLine(QPointF(x, y - 10), QPointF(x, y + 10))
            painter.setPen(QColor(255, 200, 100, 180))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(QPointF(x + 12, y - 4), "click to start measuring")
            return

        # Re-project stored lat/lon -> current pixel coords each frame so that
        # the polyline stays correct after pan or zoom.
        screen_pts = [
            canvas.lat_lon_to_px(lat, lon) for lat, lon in self._measure_latlon
        ]

        # Draw lines from placed points to current cursor
        pen_line = QPen(QColor(255, 140, 0), 2, Qt.PenStyle.SolidLine)
        pen_cursor = QPen(QColor(255, 200, 50), 2, Qt.PenStyle.DashLine)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(1, len(screen_pts)):
            painter.setPen(pen_line)
            painter.drawLine(screen_pts[i - 1], screen_pts[i])
        painter.setPen(pen_cursor)
        painter.drawLine(screen_pts[-1], self._mouse_pos)

        # Vertex dots
        painter.setBrush(QColor(255, 140, 0))
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        for pt in screen_pts:
            painter.drawEllipse(pt, 4.0, 4.0)

        # Segment distance + bearing labels (use re-projected screen_pts for positions)
        cumulative = 0.0
        seg_font = QFont("Consolas", 9)
        seg_font.setBold(True)
        painter.setFont(seg_font)
        for i in range(1, len(self._measure_latlon)):
            lat1, lon1 = self._measure_latlon[i - 1]
            lat2, lon2 = self._measure_latlon[i]
            dist = _haversine_m(lat1, lon1, lat2, lon2)
            cumulative += dist
            mid_x = (screen_pts[i - 1].x() + screen_pts[i].x()) / 2
            mid_y = (screen_pts[i - 1].y() + screen_pts[i].y()) / 2
            dist_str = _format_distance_m(dist)
            bear_str = _bearing_label(_bearing_deg(lat1, lon1, lat2, lon2))
            label = f"{dist_str}  {bear_str}"
            painter.setPen(QColor(0, 0, 0, 160))
            painter.drawText(QPointF(mid_x + 1, mid_y + 1), label)
            painter.setPen(QColor(255, 220, 50))
            painter.drawText(QPointF(mid_x, mid_y), label)

        # Total distance (and area if ≥ 3 points) at last placed point
        if len(self._measure_latlon) > 1:
            last = screen_pts[-1]
            total = f"\u03a3 {_format_distance_m(cumulative)}"
            painter.setPen(QColor(0, 0, 0, 180))
            painter.drawText(QPointF(last.x() + 9, last.y() - 9), total)
            painter.setPen(QColor(255, 240, 0))
            painter.drawText(QPointF(last.x() + 8, last.y() - 10), total)

        # Area overlay — shown when ≥ 3 points (treats the path as a closed polygon)
        if len(self._measure_latlon) >= 3:
            # Dashed closing line back to first vertex
            pen_close = QPen(QColor(255, 140, 0, 160), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_close)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(screen_pts[-1], screen_pts[0])

            # Fill the polygon with a faint tint so the enclosed area is visible
            poly = QPolygonF(screen_pts)
            painter.setBrush(QColor(255, 140, 0, 30))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(poly)

            # Compute and render the area label
            area_m2 = _spherical_area_m2(self._measure_latlon)
            if area_m2 >= 1_000_000:
                area_str = f"▣ {area_m2 / 1_000_000:.3f} km²"
            elif area_m2 >= 10_000:
                area_str = f"▣ {area_m2 / 10_000:.2f} ha"
            else:
                area_str = f"▣ {area_m2:.0f} m²"
            cx = sum(p.x() for p in screen_pts) / len(screen_pts)
            cy = sum(p.y() for p in screen_pts) / len(screen_pts)
            painter.setPen(QColor(0, 0, 0, 180))
            painter.drawText(QPointF(cx + 1, cy + 1), area_str)
            painter.setPen(QColor(255, 240, 0))
            painter.drawText(QPointF(cx, cy), area_str)

        # Bottom hint
        painter.setPen(QColor(255, 200, 100, 200))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(
            QPointF(8, canvas.height() - 8),
            "📏  click to add point  ·  Esc to clear"
        )
