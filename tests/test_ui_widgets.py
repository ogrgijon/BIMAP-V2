"""
Tests for UI widgets — requires QtTest / offscreen QApplication.
"""

from __future__ import annotations

import pytest


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
        assert "const BIMAP_DATA = window.BIMAP_DATA" not in _TEMPLATE_HELLO_WORLD

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
