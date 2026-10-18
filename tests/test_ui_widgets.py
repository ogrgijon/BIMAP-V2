"""
Tests for UI widgets — requires QtTest / offscreen QApplication.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    instance = QApplication.instance() or QApplication([])
    yield instance
    # Cancel all pending tile fetches and drain the thread pool gracefully.
    # This prevents QPixmap creation after QApplication is destroyed (qFatal).
    import bimap.ui.map_canvas.tile_fetcher as _tf
    from PyQt6.QtCore import QThreadPool
    _tf._cancelled = True
    for w in instance.topLevelWidgets():
        w.close()
    instance.processEvents()
    QThreadPool.globalInstance().waitForDone(-1)
    _tf._cancelled = False


class TestTileWidget:
    def test_instantiation(self, app):
        from bimap.ui.map_canvas.tile_widget import TileWidget
        w = TileWidget()
        assert w is not None

    def test_set_project(self, app):
        from bimap.ui.map_canvas.tile_widget import TileWidget
        from bimap.models.project import Project
        w = TileWidget()
        p = Project()
        w.set_project(p)
        assert w.center_lat == p.map_state.center_lat
        assert w.zoom == p.map_state.zoom

    def test_zoom_in_out(self, app):
        from bimap.ui.map_canvas.tile_widget import TileWidget
        from bimap.models.project import Project
        w = TileWidget()
        w.set_project(Project())
        initial_zoom = w.zoom
        w.zoom_in()
        assert w.zoom == initial_zoom + 1
        w.zoom_out()
        assert w.zoom == initial_zoom

    def test_zoom_limits(self, app):
        from bimap.ui.map_canvas.tile_widget import TileWidget
        from bimap.config import MIN_ZOOM, TILE_PROVIDERS, DEFAULT_TILE_PROVIDER
        from bimap.models.project import Project
        w = TileWidget()
        w.set_project(Project())
        provider_max = TILE_PROVIDERS.get(DEFAULT_TILE_PROVIDER, {}).get("max_zoom", 19)
        for _ in range(30):
            w.zoom_in()
        assert w.zoom == provider_max
        for _ in range(30):
            w.zoom_out()
        assert w.zoom == MIN_ZOOM

    def test_set_tool(self, app):
        from bimap.ui.map_canvas.tile_widget import TileWidget
        from bimap.ui.map_canvas.interaction import ToolMode
        w = TileWidget()
        w.set_tool(ToolMode.DRAW_POLYGON)
        assert w.interaction.tool == ToolMode.DRAW_POLYGON

    def test_set_tile_provider(self, app):
        from bimap.ui.map_canvas.tile_widget import TileWidget
        w = TileWidget()
        w.set_tile_provider("cartodb_light")
        assert w.tile_provider == "cartodb_light"

    def test_invalid_provider_ignored(self, app):
        from bimap.ui.map_canvas.tile_widget import TileWidget
        w = TileWidget()
        original = w.tile_provider
        w.set_tile_provider("nonexistent_provider")
        assert w.tile_provider == original

    def test_dismissing_empty_map_context_menu_does_not_fuse_lines(self, app, monkeypatch):
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QContextMenuEvent
        from PyQt6.QtWidgets import QMenu
        from bimap.models.project import Project
        from bimap.ui.map_canvas.tile_widget import TileWidget

        widget = TileWidget()
        widget.set_project(Project())
        actions = []
        widget.context_action_requested.connect(
            lambda action, _etype, _eid: actions.append(action)
        )
        monkeypatch.setattr(QMenu, "exec", lambda *_args, **_kwargs: None)

        event = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5)
        )
        widget.contextMenuEvent(event)

        assert "fuse" not in actions

    def test_vertex_edit_tool_emits_moved_coordinate(self, app):
        from PyQt6.QtCore import QEvent, QPointF, Qt
        from PyQt6.QtGui import QMouseEvent
        from bimap.models.project import Project
        from bimap.models.zone import LatLon, Zone, ZoneType
        from bimap.ui.map_canvas.interaction import ToolMode
        from bimap.ui.map_canvas.tile_widget import TileWidget

        widget = TileWidget()
        widget.resize(400, 300)
        project = Project()
        first = widget.px_to_lat_lon(100, 100)
        second = widget.px_to_lat_lon(300, 100)
        zone = Zone(
            zone_type=ZoneType.LINE,
            coordinates=[
                LatLon(lat=first[0], lon=first[1]),
                LatLon(lat=second[0], lon=second[1]),
            ],
        )
        project.zones.append(zone)
        widget.set_project(project)
        widget.set_tool(ToolMode.EDIT_VERTICES)
        widget.interaction.set_vertex_edit_zone(str(zone.id))
        updates = []
        widget.zone_vertices_changed.connect(
            lambda zone_id, coordinates: updates.append((zone_id, coordinates))
        )

        start = widget.lat_lon_to_px(first[0], first[1])
        target = QPointF(start.x() + 20, start.y() + 20)
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            start,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            target,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            target,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        widget.interaction.mouse_press(press, widget)
        widget.interaction.mouse_move(move, widget)
        widget.interaction.mouse_release(release, widget)

        assert len(updates) == 1
        zone_id, coordinates = updates[0]
        assert zone_id == str(zone.id)
        assert len(coordinates) == 2
        assert (coordinates[0].lat, coordinates[0].lon) == widget.px_to_lat_lon(
            target.x(), target.y()
        )

    def test_vertex_edit_can_insert_and_delete_polyline_vertices(self, app):
        from PyQt6.QtCore import QPointF
        from bimap.models.project import Project
        from bimap.models.zone import LatLon, Zone, ZoneType
        from bimap.ui.map_canvas.interaction import ToolMode
        from bimap.ui.map_canvas.tile_widget import TileWidget

        widget = TileWidget()
        widget.resize(400, 300)
        project = Project()
        widget.set_project(project)
        pixels = [(100, 100), (200, 100), (300, 200)]
        zone = Zone(
            zone_type=ZoneType.LINE,
            coordinates=[
                LatLon(
                    lat=widget.px_to_lat_lon(x, y)[0],
                    lon=widget.px_to_lat_lon(x, y)[1],
                )
                for x, y in pixels
            ],
        )
        project.zones.append(zone)
        widget.set_tool(ToolMode.EDIT_VERTICES)
        widget.interaction.set_vertex_edit_zone(str(zone.id))
        widget.zone_vertices_changed.connect(
            lambda _zone_id, coordinates: setattr(zone, "coordinates", coordinates)
        )

        point_a = widget.lat_lon_to_px(zone.coordinates[1].lat, zone.coordinates[1].lon)
        point_b = widget.lat_lon_to_px(zone.coordinates[2].lat, zone.coordinates[2].lon)
        probe = QPointF((point_a.x() + point_b.x()) / 2, (point_a.y() + point_b.y()) / 2)
        hit = widget._hit_test(probe.x(), probe.y())
        assert hit == ("zone", str(zone.id))

        widget.interaction._insert_vertex_at(probe, widget)
        assert len(zone.coordinates) == 4
        widget.interaction._vertex_selected_index = 2
        widget.interaction._delete_selected_vertex(widget)
        assert len(zone.coordinates) == 3

    def test_vertex_edit_tool_is_not_in_toolbar(self, app):
        from bimap.ui.map_canvas.interaction import ToolMode
        from bimap.ui.toolbar import MapToolbar

        toolbar = MapToolbar()
        assert ToolMode.EDIT_VERTICES not in toolbar._tool_actions

        toolbar.set_tool(ToolMode.SELECT)
        assert toolbar._tool_actions[ToolMode.SELECT].isChecked()
        toolbar.set_tool(ToolMode.EDIT_VERTICES)
        assert not any(action.isChecked() for action in toolbar._tool_actions.values())


class TestPolylineLabel:
    def test_labels_fit_segments_parallel_to_line(self, app):
        from PyQt6.QtCore import QPointF
        from bimap.models.zone import LatLon, Zone, ZoneType
        from bimap.ui.map_canvas.overlay_renderer import OverlayRenderer

        zone = Zone(
            zone_type=ZoneType.LINE,
            coordinates=[
                LatLon(lat=0, lon=0),
                LatLon(lat=100, lon=100),
                LatLon(lat=110, lon=100),
            ],
        )
        zone.label.text = "Poly"
        renderer = OverlayRenderer()
        renderer._to_px = lambda lat, lon, ctx: QPointF(lon, lat)
        painter = Mock()

        renderer._draw_zone_label(painter, zone, (0, 0, 12, 800, 600))

        assert painter.drawText.call_count == 1
        assert painter.translate.call_args.args[0] == QPointF(50, 50)
        assert painter.rotate.call_args.args[0] == pytest.approx(45)


class TestLayersPanel:
    def test_instantiation(self, app):
        from bimap.ui.panels.layers_panel import LayersPanel
        p = LayersPanel()
        assert p is not None

    def test_refresh(self, app):
        from bimap.ui.panels.layers_panel import LayersPanel
        from bimap.models.project import Project
        from bimap.models.zone import Zone
        lp = LayersPanel()
        proj = Project()
        proj.zones.append(Zone(name="Test"))
        lp.refresh(proj)   # should not raise

    def test_fuse_context_action_only_for_multiple_line_zones(self, app, monkeypatch):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QMenu
        from bimap.models.project import Project
        from bimap.models.zone import Zone, ZoneType
        from bimap.ui.panels.layers_panel import LayersPanel

        project = Project()
        lines = [
            Zone(name="Line A", zone_type=ZoneType.LINE),
            Zone(name="Line B", zone_type=ZoneType.LINE),
        ]
        polygon = Zone(name="Polygon", zone_type=ZoneType.POLYGON)
        project.zones.extend([*lines, polygon])

        panel = LayersPanel()
        panel.refresh(project)
        panel.resize(320, 500)
        panel.show()
        app.processEvents()
        layer = panel._tree.topLevelItem(0)
        rows = {
            item.data(0, Qt.ItemDataRole.UserRole): item
            for index in range(layer.childCount())
            if (item := layer.child(index)) is not None
        }
        line_rows = [rows[("zone", str(zone.id))] for zone in lines]
        polygon_row = rows[("zone", str(polygon.id))]
        shown_menus = []
        emitted_actions = []
        panel.element_action_requested.connect(
            lambda action, _etype, _eid: emitted_actions.append(action)
        )

        def capture_menu(menu, *_args):
            shown_menus.append([action.text() for action in menu.actions()])
            return None

        monkeypatch.setattr(QMenu, "exec", capture_menu)

        for row in line_rows:
            row.setSelected(True)
        menu_pos = panel._tree.visualItemRect(line_rows[0]).center()
        panel._on_context_menu(menu_pos)
        assert "Fuse Selected Lines" in shown_menus[-1]

        panel._tree.clearSelection()
        line_rows[0].setSelected(True)
        polygon_row.setSelected(True)
        panel._on_context_menu(menu_pos)
        assert "Fuse Selected Lines" not in shown_menus[-1]
        assert "fuse" not in emitted_actions
        panel.close()


class TestMainWindow:
    def test_instantiation(self, app):
        from bimap.ui.main_window import MainWindow
        w = MainWindow()
        assert w is not None

    def test_window_title(self, app):
        from bimap.ui.main_window import MainWindow
        from bimap.config import APP_NAME
        w = MainWindow()
        assert APP_NAME in w.windowTitle()

    def test_attribute_search_suggests_and_selects_zone(self, app, monkeypatch):
        from PyQt6.QtCore import Qt
        from bimap.models.data_layer import DataLayer
        from bimap.models.zone import LatLon, Zone
        from bimap.ui.main_window import MainWindow

        window = MainWindow()
        zone = Zone(
            name="Central Park",
            coordinates=[LatLon(lat=40.4, lon=-3.7), LatLon(lat=40.6, lon=-3.5)],
            metadata={"district": "Old Town"},
        )
        window._project.zones.append(zone)
        window._on_element_search_text_changed("old town")
        selected = []
        monkeypatch.setattr(
            window, "_on_element_selected",
            lambda element_type, element_id: selected.append((element_type, element_id)),
        )

        model = window._search_bar._element_suggestion_model
        assert model.rowCount() == 1
        suggestion = model.item(0)
        assert "metadata.district: Old Town" in suggestion.text()
        target = suggestion.data(Qt.ItemDataRole.UserRole)
        window._on_element_search_requested(target)

        assert window._canvas.center_lat == 40.5
        assert window._canvas.center_lon == -3.6
        assert selected == [("zone", str(zone.id))]

        source_id = "test-data-source"
        window._project.data_layers.append(DataLayer(source_id=source_id))
        window._canvas.update_data_layer_rows(
            source_id,
            [{"_lat": "41.2", "_lon": "-3.8", "business": "Cafe Rojo"}],
        )
        window._on_element_search_text_changed("cafe")
        data_suggestion = window._search_bar._element_suggestion_model.item(0)
        assert "business: Cafe Rojo" in data_suggestion.text()
        assert data_suggestion.data(Qt.ItemDataRole.UserRole) == {
            "type": "data_feature",
            "id": "0",
            "source_id": source_id,
            "row_index": 0,
        }


class TestExtensionManager:
    def test_filter_and_duplicate_keep_library_selection(self, app):
        from bimap.models.extension_template import ExtensionTemplate
        from bimap.ui.dialogs.extension_manager_dialog import ExtensionManagerDialog

        dialog = ExtensionManagerDialog([
            ExtensionTemplate(name="First", description="Overview"),
            ExtensionTemplate(name="Second", description="Details"),
        ])
        dialog._filter_edit.setText("details")

        assert dialog._list.count() == 1
        assert dialog._current_idx == 1

        dialog._duplicate_extension()

        assert len(dialog.library) == 3
        assert dialog.library[2].name == "Second (copy)"
        assert dialog._current_idx == 2
        assert dialog._list.currentItem().text() == "Second (copy)"


class TestExtensionPayload:
    def test_default_extensions_receive_object_attributes(self, app):
        from bimap.models.keypoint import Keypoint
        from bimap.models.zone import Zone, ZoneType
        from bimap.ui.dialogs.extension_editor_dialog import (
            _TEMPLATE_HELLO_WORLD,
            _build_data_payload,
        )

        zone = Zone(
            zone_type=ZoneType.RECTANGLE,
            width_m=12.5,
            height_m=8.0,
            metadata={"width_m": "12.5"},
            metadata_hidden=["width_m"],
        )
        payload = _build_data_payload(zone, "zone")
        assert payload["attributes"]["width_m"] == 12.5
        assert payload["metadata"] == {}

        keypoint = Keypoint()
        keypoint.info_card.title = "HQ"
        keypoint_payload = _build_data_payload(keypoint, "keypoint")
        assert keypoint_payload["name"] == "HQ"
        assert keypoint_payload["info_card"]["title"] == "HQ"
        assert "const MerekaiBIMAP_DATA = window.MerekaiBIMAP_DATA" not in _TEMPLATE_HELLO_WORLD

        from bimap.ui.dialogs.extension_editor_dialog import _TEMPLATES
        for template in _TEMPLATES.values():
            assert (
                "el.attributes || el.metadata" in template
                or "extensionData.attributes" in template
            )


class TestKeypointIcons:
    def test_icon_catalog_values_are_stable(self, app):
        from bimap.data.icon_font import ICON_CATALOG, icon_entry, icon_value

        assert ICON_CATALOG
        value = icon_value("tree")
        assert value == "fa:tree"
        assert icon_entry(value)[0] == "tree"

    def test_properties_panel_includes_font_icons(self, app):
        from PyQt6.QtWidgets import QComboBox
        from bimap.models.keypoint import Keypoint
        from bimap.ui.panels.properties_panel import PropertiesPanel

        panel = PropertiesPanel()
        panel.show_element(Keypoint(icon="fa:tree"), "keypoint")
        combos = panel.findChildren(QComboBox)
        assert any(combo.findData("fa:tree") >= 0 for combo in combos)

    def test_font_icon_dialog_contains_catalog(self, app):
        from bimap.data.icon_font import ICON_CATALOG
        from bimap.ui.dialogs.icon_font_dialog import IconFontDialog

        dialog = IconFontDialog()
        assert len(dialog._buttons) == len(ICON_CATALOG)
        dialog._search.setText("tree")
        assert sum(not button.isHidden() for button, _, _ in dialog._buttons) == 1
