"""
Main application window.

Wires together:
  - TileWidget (map canvas)
  - LayersPanel, PropertiesPanel, DataPanel, KeynotesPanel (dock widgets)
  - MapToolbar
  - Menu bar (File, Edit, View, Map, Data, Export, Help)
  - QUndoStack (Edit → Undo/Redo)
  - DataRefreshManager
  - Project state management (new, open, save, autosave)
"""

from __future__ import annotations

import ast
import collections
import copy
import json
import math
import operator as _op
from pathlib import Path
from typing import Any
from uuid import UUID

from PyQt6.QtCore import QSettings, QTimer, Qt, QThreadPool
from PyQt6.QtGui import QAction, QKeySequence, QPainter, QUndoStack
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStatusBar,
    QWidget,
)

from bimap.config import APP_NAME, APP_VERSION, PROJECT_FILE_EXTENSION, load_user_settings, save_user_settings, Settings
from bimap.data.icon_font import set_icon_font_family
from bimap.i18n import get_language, set_language, t
from bimap.data import DataRefreshManager, build_connector
from bimap.engine.commands import (
    AddAnnotationCommand,
    AddDataSourceCommand,
    AddKeypointCommand,
    AddZoneCommand,
    EditAnnotationCommand,
    EditKeypointCommand,
    EditZoneCommand,
    MoveElementCommand,
    RemoveAnnotationCommand,
    RemoveDataSourceCommand,
    RemoveKeypointCommand,
    RemoveMultipleCommand,
    RemoveZoneCommand,
    SetMetadataCommand,
)
from bimap.engine.live_feed_fetcher import LiveFeedFetcher
from bimap.engine.project_io import ProjectIOError, export_backup, export_elements_csv, import_backup, load_project, save_project
from bimap.models.data_source import DataSource, RefreshMode
from bimap.models.keypoint import Keypoint
from bimap.models.live_layer import LiveLayer
from bimap.models.project import Project
from bimap.models.zone import LatLon, Zone, ZoneType
from bimap.models.form_design import FieldType, FormDesign, FormField
from bimap.ui.dialogs import DataSourceDialog, DelimitationDialog, GeocodeDialog, MapComposerDialog, MetadataViewDialog
from bimap.ui.dialogs.live_layer_dialog import LiveLayerDialog
from bimap.ui.map_canvas import TileWidget, ToolMode
from bimap.ui.map_canvas.interaction import _format_distance_m, _haversine_m
from bimap.ui.panels import DataPanel, KeynotesPanel, LayersPanel, PropertiesPanel
from bimap.ui.panels.live_layers_panel import LiveLayersPanel
from bimap.ui.toolbar import MapToolbar, SearchBar
from bimap.ui._utils import _set_nested_attr, ask_question

_RECENT_FILES_KEY = "recentFiles"
_MAX_RECENT = 10

# ── Safe expression evaluator for field-mapping transforms ─────────────────────

_SAFE_BINOPS: dict = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.FloorDiv: _op.floordiv,
    ast.Mod: _op.mod,
    ast.Pow: _op.pow,
}
_SAFE_UNARYOPS: dict = {ast.USub: _op.neg, ast.UAdd: _op.pos}
_SAFE_CALLS: dict = {"str": str, "int": int, "float": float, "round": round, "abs": abs}


def _safe_eval_transform(expr: str, value: Any) -> Any:
    """Evaluate an arithmetic transform expression with ``value`` as the input.

    Supported: numeric/string literals, the name ``value``, arithmetic
    operators (+, -, *, /, //, %, **), and a whitelist of built-in calls
    (str, int, float, round, abs).  Everything else raises ``ValueError``.
    """
    tree = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> Any:
        match node:
            case ast.Constant():
                return node.value
            case ast.Name(id="value"):
                return value
            case ast.BinOp():
                fn = _SAFE_BINOPS.get(type(node.op))
                if fn is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return fn(_eval(node.left), _eval(node.right))
            case ast.UnaryOp():
                fn = _SAFE_UNARYOPS.get(type(node.op))
                if fn is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return fn(_eval(node.operand))
            case ast.Call():
                if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_CALLS:
                    raise ValueError("Only whitelisted calls are allowed: str/int/float/round/abs")
                return _SAFE_CALLS[node.func.id](*(_eval(a) for a in node.args))
            case _:
                raise ValueError(f"Unsupported expression node: {ast.dump(node)}")

    return _eval(tree.body)


def _make_general_info_form() -> FormDesign:
    """Return a pre-built General Information FormDesign for new projects."""
    return FormDesign(
        name=t("General Information"),
        description=t("Standard general-purpose information form for zones and keypoints."),
        target="both",
        fields=[
            FormField(label=t("Name"), field_type=FieldType.TEXT, required=True, default_value=""),
            FormField(label=t("Description"), field_type=FieldType.TEXTAREA, default_value=""),
            FormField(label=t("Status"), field_type=FieldType.DROPDOWN,
                      options=[t("Active"), t("Inactive"), t("Pending"), t("Under Review")],
                      default_value=t("Active")),
            FormField(label=t("Priority"), field_type=FieldType.DROPDOWN,
                      options=[t("Low"), t("Medium"), t("High"), t("Critical")],
                      default_value=t("Medium")),
            FormField(label=t("Notes"), field_type=FieldType.TEXTAREA, default_value=""),
            FormField(label=t("Tags"), field_type=FieldType.TEXT, default_value=""),
            FormField(label=t("Date"), field_type=FieldType.DATE, default_value=""),
        ],
    )


class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self._project: Project = Project()
        self._undo_stack = QUndoStack(self)
        self._refresh_manager = DataRefreshManager(self)
        self._fetcher = LiveFeedFetcher(self)
        self._shutting_down = False
        self._selected: tuple[str, str] | None = None   # (element_type, id_str)
        self._settings = QSettings(APP_NAME, APP_NAME)
        # Trail history: {layer_id: {marker_id: deque[{lat, lon}]}}
        self._live_trails: dict[str, dict[str, collections.deque]] = {}

        # Load persisted preferences
        self._prefs: Settings = load_user_settings()
        set_icon_font_family(self._prefs.keypoint_icon_font_family)

        # Apply persisted language before building any UI strings
        set_language(self._prefs.language)

        self._undo_stack.setUndoLimit(self._prefs.undo_stack_limit)

        # Debounce timer: delays the undo-command push from the rotate spinbox
        self._rotate_spinbox_timer = QTimer(self)
        self._rotate_spinbox_timer.setSingleShot(True)
        self._rotate_spinbox_timer.setInterval(400)
        self._rotate_spinbox_timer.timeout.connect(self._commit_rotate_from_spinbox)

        self._setup_ui()
        self._setup_menus()
        self._setup_autosave()
        self._connect_signals()
        self._refresh_all()

        # About-dialog triple-click counter (debug log hidden feature)
        self._about_click_count: int = 0
        self._about_click_timer = QTimer(self)
        self._about_click_timer.setSingleShot(True)
        self._about_click_timer.setInterval(1500)
        self._about_click_timer.timeout.connect(lambda: setattr(self, "_about_click_count", 0))

        self.setWindowTitle(f"{APP_NAME} — {self._project.name}")
        self.resize(1280, 800)

    # ── UI Setup ───────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        # Tool toolbar (top)
        self._toolbar = MapToolbar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._toolbar)

        # Search bar (second row in top area)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self._search_bar = SearchBar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._search_bar)

        # Central map canvas
        self._canvas = TileWidget(self)
        self._canvas.set_project(self._project)
        self.setCentralWidget(self._canvas)

        # Dock: Layers (left)
        self._layers_panel = LayersPanel()
        layers_dock = QDockWidget(t("Layers"), self)
        layers_dock.setWidget(self._layers_panel)
        layers_dock.setMinimumWidth(180)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, layers_dock)

        # Dock: Properties (right)
        self._props_panel = PropertiesPanel()
        self._props_dock = QDockWidget(t("Properties"), self)
        self._props_dock.setWidget(self._props_panel)
        self._props_dock.setMinimumWidth(220)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._props_dock)

        # Dock: Keynotes (right, below properties)
        self._keynotes_panel = KeynotesPanel()
        self._keynotes_dock = QDockWidget(t("Key Points"), self)
        self._keynotes_dock.setWidget(self._keynotes_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._keynotes_dock)

        # Dock: Data Sources (right bottom)
        self._data_panel = DataPanel()
        self._data_dock = QDockWidget(t("Data Sources"), self)
        self._data_dock.setWidget(self._data_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._data_dock)

        # Tabify right-side docks
        self.tabifyDockWidget(self._props_dock, self._keynotes_dock)
        self.tabifyDockWidget(self._keynotes_dock, self._data_dock)

        # Dock: Live Feeds (right, tabbed with data dock)
        self._live_panel = LiveLayersPanel()
        live_dock = QDockWidget(t("Live Feeds"), self)
        live_dock.setWidget(self._live_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, live_dock)
        self.tabifyDockWidget(self._data_dock, live_dock)

        # Raise Properties as the visible (active) tab on startup
        self._props_dock.raise_()

        # Status bar
        self._status_bar = self.statusBar()
        self._coord_label = QLabel("Lat: — Lon: —")
        self._zoom_label = QLabel("Zoom: —")
        self._source_label = QLabel("Sources: 0")
        self._status_bar.addPermanentWidget(self._coord_label)
        self._status_bar.addPermanentWidget(QLabel(" | "))
        self._status_bar.addPermanentWidget(self._zoom_label)
        self._status_bar.addPermanentWidget(QLabel(" | "))
        self._status_bar.addPermanentWidget(self._source_label)
        self._status_bar.addPermanentWidget(QLabel(" | "))
        self._net_label = QLabel("🌐 Online")
        self._status_bar.addPermanentWidget(self._net_label)
        self._refresh_tiles_btn = QPushButton("↻ Refresh")
        self._refresh_tiles_btn.setFixedHeight(18)
        self._refresh_tiles_btn.setToolTip(t("Refresh map tiles"))
        self._refresh_tiles_btn.clicked.connect(self._canvas.refresh_tiles)
        self._refresh_tiles_btn.setVisible(False)
        self._status_bar.addPermanentWidget(self._refresh_tiles_btn)

    def _setup_menus(self) -> None:
        mb = self.menuBar()

        # ── File ────────────────────────────────
        file_menu = mb.addMenu(t("File"))
        act_new = QAction(t("New Project"), self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(self._cmd_new)
        file_menu.addAction(act_new)

        act_open = QAction(t("Open…"), self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._cmd_open)
        file_menu.addAction(act_open)

        # Recent files sub-menu
        self._recent_menu = file_menu.addMenu(t("Recent Projects"))
        self._rebuild_recent_menu()

        file_menu.addSeparator()

        act_save = QAction(t("Save"), self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._cmd_save)
        file_menu.addAction(act_save)

        act_save_as = QAction(t("Save As…"), self)
        act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_save_as.triggered.connect(self._cmd_save_as)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()
        act_import = QAction(t("Import GeoJSON…"), self)
        act_import.triggered.connect(self._cmd_import_geojson)
        file_menu.addAction(act_import)

        act_export_geojson = QAction(t("Export GeoJSON…"), self)
        act_export_geojson.setToolTip(t("Export all zones and keypoints as a GeoJSON file"))
        act_export_geojson.triggered.connect(self._cmd_export_geojson)
        file_menu.addAction(act_export_geojson)

        file_menu.addSeparator()
        act_backup_exp = QAction(t("📤  Export Data Backup…"), self)
        act_backup_exp.setToolTip(t("Save a portable backup file you can transfer to another PC"))
        act_backup_exp.triggered.connect(self._cmd_export_backup)
        file_menu.addAction(act_backup_exp)
        act_backup_imp = QAction(t("📥  Import Data Backup…"), self)
        act_backup_imp.setToolTip(t("Load a backup or .bimap file and replace the current project"))
        act_backup_imp.triggered.connect(self._cmd_import_backup)
        file_menu.addAction(act_backup_imp)

        act_export_csv = QAction(t("📊  Export Elements CSV…"), self)
        act_export_csv.setToolTip(t("Export all zones and keypoints with their attributes to CSV"))
        act_export_csv.triggered.connect(self._cmd_export_elements_csv)
        file_menu.addAction(act_export_csv)

        file_menu.addSeparator()
        act_export = QAction(t("Print / Export PDF…"), self)
        act_export.setShortcut(QKeySequence("Ctrl+P"))
        act_export.triggered.connect(self._cmd_print_export)
        file_menu.addAction(act_export)

        file_menu.addSeparator()
        act_quit = QAction(t("Quit"), self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(QApplication.quit)
        file_menu.addAction(act_quit)

        # ── Edit ────────────────────────────────
        edit_menu = mb.addMenu(t("Edit"))
        act_undo = self._undo_stack.createUndoAction(self, t("Undo"))
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(act_undo)

        act_redo = self._undo_stack.createRedoAction(self, t("Redo"))
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(act_redo)

        edit_menu.addSeparator()
        act_del = QAction(t("Delete Selected"), self)
        act_del.setShortcut(QKeySequence.StandardKey.Delete)
        act_del.triggered.connect(self._cmd_delete_selected)
        edit_menu.addAction(act_del)

        # ── Single-key map tool shortcuts ─────────────────────────────────
        _tool_shortcuts = [
            ("Cursor / Select", "C", ToolMode.SELECT),
            ("Pan", "H", ToolMode.PAN),
            ("Rotate", "R", ToolMode.ROTATE_ELEMENT),
            ("Move", "G", ToolMode.MOVE_ELEMENT),
            ("Lasso Selector", "L", ToolMode.MAGIC_WAND),
        ]
        for label, shortcut, mode in _tool_shortcuts:
            act = QAction(t(label), self)
            act.setShortcut(QKeySequence(shortcut))
            act.triggered.connect(lambda _checked=False, m=mode: self._canvas.set_tool(m))
            edit_menu.addAction(act)

        # ── Create (quick access for new users) ──
        edit_menu.addSeparator()
        _create_tools = [
            ("Draw Polygon Zone",    "Ctrl+Shift+P", "P", ToolMode.DRAW_POLYGON),
            ("Draw Rectangle Zone", "Ctrl+Shift+R", "B", ToolMode.DRAW_RECTANGLE),
            ("Draw Circle Zone",     "Ctrl+Shift+C", "O", ToolMode.DRAW_CIRCLE),
            ("Place Keypoint",       "Ctrl+Shift+K", "K", ToolMode.DRAW_KEYPOINT),
            ("Place Text Annotation","Ctrl+Shift+T", "T", ToolMode.DRAW_TEXT),
        ]
        for label, shortcut, quick_shortcut, mode in _create_tools:
            act = QAction(t(label), self)
            act.setToolTip(t(label))
            act.setShortcuts([QKeySequence(shortcut), QKeySequence(quick_shortcut)])
            act.triggered.connect(lambda _checked=False, m=mode: self._canvas.set_tool(m))
            edit_menu.addAction(act)

        edit_menu.addSeparator()
        act_prefs = QAction(t("Preferences…"), self)
        act_prefs.setShortcut(QKeySequence("Ctrl+,"))
        act_prefs.triggered.connect(self._cmd_preferences)
        edit_menu.addAction(act_prefs)

        # ── View ────────────────────────────────
        view_menu = mb.addMenu(t("View"))
        act_save_bm = QAction(t("Save Bookmark…"), self)
        act_save_bm.setShortcut(QKeySequence("Ctrl+B"))
        act_save_bm.triggered.connect(self._cmd_save_bookmark)
        view_menu.addAction(act_save_bm)

        self._bookmarks_menu = view_menu.addMenu(t("Bookmarks"))
        self._rebuild_bookmarks_menu()

        view_menu.addSeparator()
        act_show_keynotes = QAction(t("Show Key Points"), self)
        act_show_keynotes.setShortcut(QKeySequence("Ctrl+Shift+N"))
        act_show_keynotes.triggered.connect(
            lambda: (self._keynotes_dock.show(), self._keynotes_dock.raise_())
        )
        view_menu.addAction(act_show_keynotes)

        act_show_data = QAction(t("Show Data Sources"), self)
        act_show_data.setShortcut(QKeySequence("Ctrl+Shift+D"))
        act_show_data.triggered.connect(
            lambda: (self._data_dock.show(), self._data_dock.raise_())
        )
        view_menu.addAction(act_show_data)

        # ── Map ─────────────────────────────────
        map_menu = mb.addMenu(t("Map"))
        act_search = QAction(t("Search Location…"), self)
        act_search.setShortcut(QKeySequence("Ctrl+F"))
        act_search.triggered.connect(self._cmd_search_location)
        map_menu.addAction(act_search)

        act_zoom_in = QAction(t("Zoom In"), self)
        act_zoom_in.setShortcut(QKeySequence("+"))
        act_zoom_in.triggered.connect(self._cmd_zoom_in)
        map_menu.addAction(act_zoom_in)

        act_zoom_out = QAction(t("Zoom Out"), self)
        act_zoom_out.setShortcut(QKeySequence("-"))
        act_zoom_out.triggered.connect(self._cmd_zoom_out)
        map_menu.addAction(act_zoom_out)

        map_menu.addSeparator()
        act_delimit = QAction(t("Set Delimitation…"), self)
        act_delimit.triggered.connect(self._cmd_set_delimitation)
        map_menu.addAction(act_delimit)

        act_clear_delimit = QAction(t("Clear Delimitation"), self)
        act_clear_delimit.triggered.connect(self._cmd_clear_delimitation)
        map_menu.addAction(act_clear_delimit)

        map_menu.addSeparator()
        act_goto_coords = QAction(t("Place by Coordinates…"), self)
        act_goto_coords.setShortcut(QKeySequence("Ctrl+G"))
        act_goto_coords.triggered.connect(self._cmd_goto_coords)
        map_menu.addAction(act_goto_coords)

        map_menu.addSeparator()
        act_offline = QAction(t("Offline Map…"), self)
        act_offline.setToolTip(t("Download and cache map tiles for the current region so the map works without internet access"))
        act_offline.triggered.connect(self._cmd_work_offline)
        map_menu.addAction(act_offline)

        # ── Data ────────────────────────────────
        data_menu = mb.addMenu(t("Data"))
        act_add_src = QAction(t("Add Data Source…"), self)
        act_add_src.triggered.connect(self._cmd_add_data_source)
        data_menu.addAction(act_add_src)

        act_refresh_all = QAction(t("Refresh All Sources"), self)
        act_refresh_all.triggered.connect(self._cmd_refresh_all_sources)
        data_menu.addAction(act_refresh_all)

        data_menu.addSeparator()
        act_ext_lib = QAction(t("Manage Extensions") + "…", self)
        act_ext_lib.setToolTip(t("Open the HTML5/CSS/JS Extension Library manager"))
        act_ext_lib.triggered.connect(self._cmd_extension_library)
        data_menu.addAction(act_ext_lib)

        act_form_designer = QAction(t("Form Designer…"), self)
        act_form_designer.setToolTip(t("Design forms to fill in on zones and keypoints"))
        act_form_designer.triggered.connect(self._cmd_form_designer)
        data_menu.addAction(act_form_designer)

        # ── External Data ────────────────────────────────
        ext_menu = mb.addMenu(t("External Data"))

        act_add_wfs = QAction(t("Add WFS Source…"), self)
        act_add_wfs.setToolTip(t("Connect to an OGC WFS service and add a feature layer"))
        act_add_wfs.triggered.connect(self._cmd_add_wfs_source)
        ext_menu.addAction(act_add_wfs)

        ext_menu.addSeparator()
        act_ogc_browser = QAction(t("Browse OGC Catalog…"), self)
        act_ogc_browser.setToolTip(t("Search an OGC CSW catalogue (e.g. IDEE Spain) and add WFS layers as data sources"))
        act_ogc_browser.triggered.connect(self._cmd_ogc_browser)
        ext_menu.addAction(act_ogc_browser)

        ext_menu.addSeparator()
        act_import_pack = QAction(t("Import Source Pack…"), self)
        act_import_pack.setToolTip(t("Open a .bsp source pack file and add its entries as data sources"))
        act_import_pack.triggered.connect(self._cmd_import_source_pack)
        ext_menu.addAction(act_import_pack)

        act_export_pack = QAction(t("Export Source Pack…"), self)
        act_export_pack.setToolTip(t("Bundle selected project data sources into a shareable .bsp pack file"))
        act_export_pack.triggered.connect(self._cmd_export_source_pack)
        ext_menu.addAction(act_export_pack)

        ext_menu.addSeparator()
        live_menu = ext_menu.addMenu(t("Live Feeds") + " ▸")
        act_add_live = QAction(t("add_live_feed") + "…", self)
        act_add_live.triggered.connect(self._cmd_add_live_feed)
        live_menu.addAction(act_add_live)

        act_manage_live = QAction(t("manage_live_feeds") + "…", self)
        act_manage_live.triggered.connect(self._cmd_manage_live_feeds)
        live_menu.addAction(act_manage_live)

        # ── Measurement ─────────────────────────────────────────────────────────
        meas_menu = mb.addMenu(t("Measurement"))

        act_start_meas = QAction(t("Start Measuring"), self)
        act_start_meas.setShortcut(QKeySequence("M"))
        act_start_meas.triggered.connect(
            lambda: self._canvas.set_tool(ToolMode.MEASURE)
        )
        meas_menu.addAction(act_start_meas)

        act_dimension = QAction(t("Place Dimension"), self)
        act_dimension.setShortcut(QKeySequence("D"))
        act_dimension.triggered.connect(
            lambda: self._canvas.set_tool(ToolMode.DIMENSION)
        )
        meas_menu.addAction(act_dimension)

        act_clear_meas = QAction(t("Clear Measurement"), self)
        act_clear_meas.setShortcut(QKeySequence("Ctrl+M"))
        act_clear_meas.triggered.connect(self._cmd_clear_measurement)
        meas_menu.addAction(act_clear_meas)

        # ── Help ────────────────────────────────
        help_menu = mb.addMenu(t("Help"))

        # Language sub-menu
        lang_menu = help_menu.addMenu(t("Language"))
        act_lang_en = QAction(t("English"), self)
        act_lang_en.setCheckable(True)
        act_lang_en.setChecked(get_language() == "en")
        act_lang_en.triggered.connect(lambda: self._cmd_set_language("en"))
        lang_menu.addAction(act_lang_en)

        act_lang_es = QAction(t("Spanish"), self)
        act_lang_es.setCheckable(True)
        act_lang_es.setChecked(get_language() == "es")
        act_lang_es.triggered.connect(lambda: self._cmd_set_language("es"))
        lang_menu.addAction(act_lang_es)

        help_menu.addSeparator()
        act_about = QAction(t("About BIMAP"), self)
        act_about.triggered.connect(self._cmd_about)
        help_menu.addAction(act_about)

    def _setup_autosave(self) -> None:
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(self._prefs.autosave_interval_ms)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()
        # WFS viewport-tracking: re-fetch after 700 ms of pan/zoom inactivity
        self._wfs_viewport_debounce = QTimer(self)
        self._wfs_viewport_debounce.setSingleShot(True)
        self._wfs_viewport_debounce.setInterval(700)
        self._wfs_viewport_debounce.timeout.connect(self._on_wfs_viewport_refresh)

    # ── Signal connections ─────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        # Toolbar
        self._toolbar.tool_selected.connect(self._on_tool_selected)
        self._toolbar.import_requested.connect(self._cmd_import_geojson)
        self._toolbar.print_requested.connect(self._cmd_print_export)
        self._toolbar.toggle_grid_requested.connect(self._on_toggle_grid)
        self._toolbar.rotate_degree_changed.connect(self._on_rotate_degree_from_toolbar)
        # Search bar
        self._search_bar.tile_provider_changed.connect(self._on_provider_changed)
        self._search_bar.zoom_in_requested.connect(self._cmd_zoom_in)
        self._search_bar.zoom_out_requested.connect(self._cmd_zoom_out)
        self._search_bar.search_requested.connect(self._on_search_requested)

        # Map canvas
        self._canvas.viewport_changed.connect(self._on_viewport_changed)
        self._canvas.tool_changed.connect(
            lambda mode: self._toolbar.set_tool(ToolMode(mode))
        )
        self._canvas.draw_finished.connect(self._on_draw_finished)
        self._canvas.element_selected.connect(self._on_element_selected)
        self._canvas.coordinates_changed.connect(self._on_coords_changed)
        self._canvas.context_action_requested.connect(self._on_context_action)
        self._canvas.multi_select_finished.connect(self._on_multi_select)
        self._canvas.element_move_dropped.connect(self._on_element_move_dropped)
        self._canvas.add_annotation_requested.connect(self._on_add_annotation_at)
        self._canvas.open_extension_requested.connect(self._on_open_extension)
        self._canvas.element_rotated.connect(self._on_element_rotated)
        self._canvas.network_status_changed.connect(self._on_network_status_changed)
        self._canvas.data_feature_selected.connect(self._on_data_feature_selected)

        # Layers panel
        self._layers_panel.element_selected.connect(self._on_element_selected)
        self._layers_panel.element_visibility_changed.connect(self._on_visibility_changed)
        self._layers_panel.element_delete_requested.connect(
            lambda et, eid: self._delete_element(et, eid)
        )
        self._layers_panel.layer_visibility_changed.connect(self._on_layer_visibility_changed)
        self._layers_panel.data_layer_visibility_changed.connect(
            self._on_data_layer_visibility_changed
        )
        self._layers_panel.data_layer_opacity_changed.connect(
            self._on_data_layer_opacity_changed
        )
        self._layers_panel.data_layer_edit_requested.connect(self._cmd_edit_data_source)
        self._layers_panel.layer_add_requested.connect(self._on_layer_add_requested)
        self._layers_panel.layer_remove_requested.connect(self._on_layer_remove_requested)
        self._layers_panel.element_action_requested.connect(self._on_layer_element_action)
        self._layers_panel.element_layer_changed.connect(self._on_element_layer_changed)

        # Properties panel
        self._props_panel.element_changed.connect(self._on_property_changed)
        self._props_panel.preset_applied.connect(self._on_preset_applied)
        self._props_panel.metadata_changed.connect(self._on_metadata_changed)
        self._props_panel.metadata_hidden_changed.connect(self._on_metadata_hidden_changed)
        self._props_panel.metadata_binding_changed.connect(self._on_metadata_binding_changed)
        self._props_panel.open_form_designer_requested.connect(self._cmd_form_designer)

        # Keynotes panel
        self._keynotes_panel.assign_keynote_requested.connect(self._assign_keynote)
        self._keynotes_panel.clear_keynote_requested.connect(self._clear_keynote)
        self._keynotes_panel.keynote_selected.connect(
            lambda eid: self._on_element_selected("keypoint", eid)
        )

        # Data panel
        self._data_panel.add_requested.connect(self._cmd_add_data_source)
        self._data_panel.edit_requested.connect(self._cmd_edit_data_source)
        self._data_panel.remove_requested.connect(self._cmd_remove_data_source)
        self._data_panel.refresh_requested.connect(self._refresh_manager.refresh_now)
        self._data_panel.fit_requested.connect(self._on_fit_data_source)

        # Live feed fetcher
        self._fetcher.positions_updated.connect(self._on_live_positions_updated)
        self._fetcher.fetch_error.connect(self._on_live_fetch_error)

        # Live layers panel
        self._live_panel.layer_add_requested.connect(self._cmd_add_live_feed)
        self._live_panel.layer_edit_requested.connect(self._cmd_edit_live_feed)
        self._live_panel.layer_toggle_requested.connect(self._cmd_toggle_live_feed)
        self._live_panel.layer_remove_requested.connect(self._cmd_remove_live_feed)

        # Refresh manager
        self._refresh_manager.data_refreshed.connect(self._on_data_refreshed)
        self._refresh_manager.refresh_error.connect(self._on_refresh_error)
        self._refresh_manager.refresh_started.connect(self._on_refresh_started)
        self._refresh_manager.refresh_stats.connect(self._on_refresh_stats)

    # ── Refresh / update helpers ───────────────────────────────────────────────

    def _refresh_all(self) -> None:
        self._layers_panel.refresh(self._project)
        self._keynotes_panel.refresh(self._project)
        self._data_panel.refresh(self._project)
        self._live_panel.load_layers(self._project.live_layers)
        self._canvas.update()
        self._zoom_label.setText(f"Zoom: {self._project.map_state.zoom}")
        self._source_label.setText(f"Sources: {len(self._project.data_sources)}")
        # Defer properties panel rebuild to avoid segfault when called from
        # inside a signal handler (e.g. QDoubleSpinBox editingFinished).
        QTimer.singleShot(0, self._props_panel.refresh_current)

    def _set_project(self, project: Project) -> None:
        self._fetcher.stop_all()
        self._canvas._live_positions.clear()
        self._project = project
        self._undo_stack.clear()
        # Ensure RECTANGLE zones have their width_m / height_m derived
        # (older projects may have been saved before dimension tracking was added).
        for _zone in project.zones:
            if getattr(_zone, "zone_type", None) == "rectangle":
                _update_zone_derived_attrs(_zone)
        self._canvas.set_project(project)
        self._props_panel.set_project(project)
        self._search_bar.set_tile_provider(project.map_state.tile_provider)
        self._refresh_all()
        self._rebuild_bookmarks_menu()
        self.setWindowTitle(f"{APP_NAME} — {project.name}")

    # ── Commands (menu / toolbar actions) ─────────────────────────────────────

    def _cmd_new(self) -> None:
        if not self._confirm_discard():
            return
        project = Project()
        project.form_designs.append(_make_general_info_form())
        self._set_project(project)

    # ── Shared helper callbacks ──────────────────────────────────────────────

    def _notify_canvas(self) -> None:
        """Refresh canvas, layers panel, and properties panel — used as the
        notify callback in all undo commands so undo/redo keeps every view live."""
        self._canvas.update()
        self._layers_panel.refresh(self._project)
        # Defer the panel rebuild to the next event-loop tick.  If this is
        # called from inside a widget signal handler (e.g. QDoubleSpinBox
        # editingFinished), the C++ widget would otherwise be destroyed while
        # still on the call stack, causing a segfault that Python cannot catch.
        QTimer.singleShot(0, self._props_panel.refresh_current)

    def _load_file(self, path: str) -> None:
        """Load a project file, update recent list, and show errors in a dialog."""
        try:
            project = load_project(Path(path))
            self._set_project(project)
            self._add_recent(path)
        except (ProjectIOError, FileNotFoundError) as exc:
            QMessageBox.critical(self, t("Open Failed"), str(exc))

    def _open_ext_viewer(self, etype: str, eid: str) -> None:
        """Open the Extension viewer dialog for the given element."""
        element = self._find_element(etype, eid)
        if element:
            from bimap.ui.dialogs.extension_viewer_dialog import ExtensionViewerDialog
            dlg = ExtensionViewerDialog(element, etype, self)
            dlg.show()

    def _cmd_open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, t("Open Project"), "",
            f"BIMAP Projects (*{PROJECT_FILE_EXTENSION});;All Files (*.*)"
        )
        if not path:
            return
        self._load_file(path)

    def _cmd_save(self) -> None:
        if self._project.file_path:
            self._save_to(Path(self._project.file_path))
        else:
            self._cmd_save_as()

    def _cmd_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, t("Save Project As"), self._project.name,
            f"BIMAP Projects (*{PROJECT_FILE_EXTENSION})"
        )
        if path:
            self._save_to(Path(path))

    def _save_to(self, path: Path) -> None:
        # Sync canvas viewport back to project
        self._project.map_state.center_lat = self._canvas.center_lat
        self._project.map_state.center_lon = self._canvas.center_lon
        self._project.map_state.zoom = self._canvas.zoom
        try:
            save_project(self._project, path)
            self._add_recent(str(path))
            self.setWindowTitle(f"{APP_NAME} — {self._project.name}")
            self.statusBar().showMessage(f"Saved: {path}", 3000)
        except ProjectIOError as exc:
            QMessageBox.critical(self, t("Save Failed"), str(exc))

    def _autosave(self) -> None:
        if self._project.file_path and not self._undo_stack.isClean():
            self._save_to(Path(self._project.file_path))

    def _cmd_print_export(self) -> None:
        """Open Map Composer — user can then choose Export PDF or Print."""
        layer_names = [z.name for z in self._project.zones]
        dlg = MapComposerDialog(
            layout=self._project.pdf_layout,
            current_zoom=self._project.map_state.zoom,
            layer_names=layer_names,
            parent=self,
            canvas_widget=self._canvas,
            project_layers=self._project.zones,
            project_name=getattr(self._project, "name", ""),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.accepted_as == "export":
            from bimap.engine.pdf_renderer import render_pdf
            try:
                render_pdf(self._project, dlg.output_path)
                self.statusBar().showMessage(f"PDF exported → {dlg.output_path}", 6000)
            except Exception as exc:
                QMessageBox.critical(self, t("Export Failed"), str(exc))
        else:
            try:
                preview = QPrintPreviewDialog(self)
                preview.resize(900, 700)
                preview.paintRequested.connect(self._print_map)
                preview.exec()
            except Exception as exc:
                QMessageBox.critical(self, t("Print Error"), str(exc))

    def _print_map(self, printer: "QPrinter") -> None:
        from bimap.engine.pdf_renderer import _render_page
        pr = printer.pageRect(QPrinter.Unit.DevicePixel).toRect()
        painter = QPainter(printer)
        _render_page(painter, self._project, pr.width(), pr.height(), printer.resolution())
        painter.end()

    def _cmd_import_geojson(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, t("Import GeoJSON"), "", "GeoJSON Files (*.geojson *.json);;All Files (*.*)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            features = data.get("features", []) if data.get("type") == "FeatureCollection" else []
            imported = 0
            for feat in features:
                geom = feat.get("geometry", {})
                props = feat.get("properties") or {}
                name = (props.get("name") or props.get("title")
                        or props.get("Name") or "Zone")
                coords_raw = geom.get("coordinates", [])
                gtype = geom.get("type", "")
                if gtype == "Polygon" and coords_raw:
                    ring = coords_raw[0]
                    coords = [LatLon(lat=c[1], lon=c[0]) for c in ring]
                    zone = Zone(name=name, zone_type=ZoneType.POLYGON, coordinates=coords)
                    zone.label.text = name
                    cmd = AddZoneCommand(self._project, zone, self._refresh_all)
                    self._undo_stack.push(cmd)
                    imported += 1
                elif gtype == "MultiPolygon" and coords_raw:
                    for poly in coords_raw:
                        ring = poly[0]
                        coords = [LatLon(lat=c[1], lon=c[0]) for c in ring]
                        zone = Zone(name=name, zone_type=ZoneType.POLYGON, coordinates=coords)
                        zone.label.text = name
                        cmd = AddZoneCommand(self._project, zone, self._refresh_all)
                        self._undo_stack.push(cmd)
                        imported += 1
            self.statusBar().showMessage(f"GeoJSON: imported {imported} zone(s).", 4000)
        except Exception as exc:
            QMessageBox.critical(self, t("Import Failed"), str(exc))

    def _cmd_export_geojson(self) -> None:
        """Export all zones and keypoints as a GeoJSON FeatureCollection."""
        import math as _math
        import json as _json

        path, _ = QFileDialog.getSaveFileName(
            self, t("Export GeoJSON"), "", "GeoJSON Files (*.geojson);;JSON Files (*.json);;All Files (*.*)"
        )
        if not path:
            return
        if not (path.lower().endswith(".geojson") or path.lower().endswith(".json")):
            path += ".geojson"

        features: list[dict] = []

        # ── Zones ──────────────────────────────────────────────────────────── #
        for zone in self._project.zones:
            props: dict = {
                "name": zone.name,
                "zone_type": str(zone.zone_type).split(".")[-1],
                "group": zone.group,
                "layer": zone.layer,
                "visible": zone.visible,
            }
            # metadata (skip hidden keys)
            hidden = set(getattr(zone, "metadata_hidden", []))
            for k, v in (zone.metadata or {}).items():
                if k not in hidden:
                    props[k] = v

            zt = str(zone.zone_type)
            if "circle" in zt and zone.coordinates:
                # Approximate circle as 64-sided polygon
                c = zone.coordinates[0]
                props["radius_m"] = zone.radius_m
                R = 6_371_000.0
                n = 64
                ring = []
                for i in range(n + 1):
                    bearing = 2 * _math.pi * i / n
                    lat_r = _math.radians(c.lat)
                    dlat = zone.radius_m / R
                    dlon = zone.radius_m / (R * _math.cos(lat_r))
                    lat2 = c.lat + _math.degrees(dlat * _math.cos(bearing))
                    lon2 = c.lon + _math.degrees(dlon * _math.sin(bearing))
                    ring.append([round(lon2, 7), round(lat2, 7)])
                geometry = {"type": "Polygon", "coordinates": [ring]}
            elif zone.coordinates:
                ring = [[round(c.lon, 7), round(c.lat, 7)] for c in zone.coordinates]
                if ring and ring[0] != ring[-1]:
                    ring.append(ring[0])  # close ring
                geometry = {"type": "Polygon", "coordinates": [ring]}
            else:
                continue  # skip zones with no geometry

            features.append({"type": "Feature", "geometry": geometry, "properties": props})

        # ── Keypoints ─────────────────────────────────────────────────────── #
        for kp in self._project.keypoints:
            props = {
                "name": kp.name,
                "type": "keypoint",
                "group": getattr(kp, "group", ""),
                "layer": getattr(kp, "layer", "Default"),
            }
            hidden = set(getattr(kp, "metadata_hidden", []))
            for k, v in (kp.metadata or {}).items():
                if k not in hidden:
                    props[k] = v
            geometry = {"type": "Point", "coordinates": [round(kp.lon, 7), round(kp.lat, 7)]}
            features.append({"type": "Feature", "geometry": geometry, "properties": props})

        collection = {
            "type": "FeatureCollection",
            "name": self._project.name,
            "features": features,
        }
        try:
            Path(path).write_text(
                _json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.statusBar().showMessage(
                f"GeoJSON exported: {len(features)} feature(s) → {path}", 5000
            )
        except Exception as exc:
            QMessageBox.critical(self, t("Export Failed"), str(exc))

    def _cmd_export_backup(self) -> None:
        """Export the current project as a portable ZIP backup file."""
        path, _ = QFileDialog.getSaveFileName(
            self, t("Export Data Backup"), "", "BIMAP Backup (*.bimap.zip);;All Files (*.*)"
        )
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        try:
            export_backup(self._project, Path(path))
            QMessageBox.information(
                self, t("Backup Exported"),
                t("Backup saved to:\n{path}\n\nCopy this file to transfer your project to another PC.").format(path=path)
            )
        except Exception as exc:
            QMessageBox.critical(self, t("Export Failed"), str(exc))

    def _cmd_export_elements_csv(self) -> None:
        """Export all zones and keypoints with every attribute to a CSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self, t("Export Elements CSV"), "", "CSV Files (*.csv);;All Files (*.*)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            export_elements_csv(self._project, Path(path))
            n_zones = len(self._project.zones)
            n_kps = len(self._project.keypoints)
            QMessageBox.information(
                self,
                t("CSV Exported"),
                f"{t('Exported')} {n_zones} {t('zone(s)')} {t('and')} "
                f"{n_kps} {t('keypoint(s)')} {t('to')}:\n{path}",
            )
        except Exception as exc:
            QMessageBox.critical(self, t("Export Failed"), str(exc))

    def _cmd_import_backup(self) -> None:
        """Load a project from a ZIP backup or .bimap file, replacing the current project."""
        path, _ = QFileDialog.getOpenFileName(
            self, t("Import Data Backup"),
            "", "Backup / Project files (*.bimap.zip *.zip *.bimap);;All Files (*.*)"
        )
        if not path:
            return
        reply = ask_question(
            self, t("Replace Project?"),
            t("This will replace the current project with the backup.\nUnsaved changes will be lost. Continue?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            project = import_backup(Path(path))
            self._set_project(project)
            self.statusBar().showMessage(t("Backup imported successfully."), 4000)
        except Exception as exc:
            QMessageBox.critical(self, t("Import Failed"), str(exc))

    def _cmd_save_bookmark(self) -> None:
        name, ok = QInputDialog.getText(self, t("Save Bookmark"), t("Bookmark name:"))
        if ok and name.strip():
            bm = {
                "name": name.strip(),
                "lat": self._canvas.center_lat,
                "lon": self._canvas.center_lon,
                "zoom": self._canvas.zoom,
            }
            bookmarks = getattr(self._project.map_state, "bookmarks", [])
            bookmarks.append(bm)
            self._project.mark_modified()
            self._rebuild_bookmarks_menu()

    def _rebuild_bookmarks_menu(self) -> None:
        self._bookmarks_menu.clear()
        bookmarks = getattr(self._project.map_state, "bookmarks", [])
        if not bookmarks:
            no_action = QAction("(no bookmarks)", self)
            no_action.setEnabled(False)
            self._bookmarks_menu.addAction(no_action)
            return
        for bm in bookmarks:
            act = QAction(bm["name"], self)
            lat, lon, zoom = bm["lat"], bm["lon"], bm["zoom"]
            act.triggered.connect(lambda _=False, la=lat, lo=lon, z=zoom:
                                  self._canvas.set_viewport(la, lo, z))
            self._bookmarks_menu.addAction(act)

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        paths = self._settings.value(_RECENT_FILES_KEY, []) or []
        if not paths:
            act = QAction("(no recent files)", self)
            act.setEnabled(False)
            self._recent_menu.addAction(act)
            return
        for p in paths:
            act = QAction(p, self)
            act.triggered.connect(lambda _=False, path=p: self._open_recent(path))
            self._recent_menu.addAction(act)
        self._recent_menu.addSeparator()
        clr = QAction("Clear Recent", self)
        clr.triggered.connect(self._clear_recent)
        self._recent_menu.addAction(clr)

    def _add_recent(self, path: str) -> None:
        paths = list(self._settings.value(_RECENT_FILES_KEY, []) or [])
        if path in paths:
            paths.remove(path)
        paths.insert(0, path)
        paths = paths[:_MAX_RECENT]
        self._settings.setValue(_RECENT_FILES_KEY, paths)
        self._rebuild_recent_menu()

    def _clear_recent(self) -> None:
        self._settings.remove(_RECENT_FILES_KEY)
        self._rebuild_recent_menu()

    def _open_recent(self, path: str) -> None:
        if not self._confirm_discard():
            return
        self._load_file(path)

    def _cmd_delete_selected(self) -> None:
        if self._selected:
            self._delete_element(*self._selected)

    def _cmd_search_location(self) -> None:
        dlg = GeocodeDialog(self)
        if dlg.exec() == dlg.DialogCode.Accepted and dlg.result:
            r = dlg.result
            self._canvas.set_viewport(r.lat, r.lon, self._canvas.zoom)

    def _on_search_requested(self, query: str) -> None:
        """Run a geocode query from the toolbar search bar in a background thread."""
        from bimap.engine.geocoding import GeocoderWorker
        worker = GeocoderWorker(query)
        worker.signals.result.connect(
            lambda r: self._canvas.set_viewport(r.lat, r.lon, self._canvas.zoom)
        )
        worker.signals.error.connect(
            lambda msg: self.statusBar().showMessage(msg, 3000)
        )
        QThreadPool.globalInstance().start(worker)

    def _cmd_clear_measurement(self) -> None:
        """Clear the current measurement overlay without changing the active tool."""
        handler = self._canvas._interaction
        handler._measure_pts.clear()
        handler._measure_latlon.clear()
        handler.request_repaint.emit()

    def _cmd_zoom_in(self) -> None:
        self._canvas.set_viewport(
            self._canvas.center_lat,
            self._canvas.center_lon,
            self._canvas.zoom + 1,
        )

    def _cmd_zoom_out(self) -> None:
        self._canvas.set_viewport(
            self._canvas.center_lat,
            self._canvas.center_lon,
            self._canvas.zoom - 1,
        )

    # ── Live Feed commands ─────────────────────────────────────────────────────

    def _cmd_add_live_feed(self) -> None:
        dlg = LiveLayerDialog(parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            layer = dlg.result_layer()
            self._project.live_layers.append(layer)
            self._project.mark_modified()
            self._live_panel.load_layers(self._project.live_layers)
            if layer.visible:
                self._fetcher.start(layer)
                self._live_panel.set_status(layer.id, "polling")

    def _cmd_edit_live_feed(self, layer_id: str) -> None:
        existing = next(
            (l for l in self._project.live_layers if l.id == layer_id), None
        )
        if not existing:
            return
        dlg = LiveLayerDialog(layer=existing, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            updated = dlg.result_layer()
            idx = next(
                i for i, l in enumerate(self._project.live_layers) if l.id == layer_id
            )
            self._project.live_layers[idx] = updated
            self._project.mark_modified()
            self._live_panel.load_layers(self._project.live_layers)
            if updated.visible:
                self._fetcher.start(updated)   # restarts with new config
                self._live_panel.set_status(layer_id, "polling")
            else:
                self._fetcher.stop(layer_id)
                self._canvas.clear_live_positions(layer_id)
                self._live_panel.set_status(layer_id, "paused")

    def _cmd_toggle_live_feed(self, layer_id: str) -> None:
        if self._fetcher.is_active(layer_id):
            self._fetcher.stop(layer_id)
            self._canvas.clear_live_positions(layer_id)
            self._live_panel.set_status(layer_id, "paused")
        else:
            layer = next(
                (l for l in self._project.live_layers if l.id == layer_id), None
            )
            if layer:
                self._fetcher.start(layer)
                self._live_panel.set_status(layer_id, "polling")

    def _cmd_remove_live_feed(self, layer_id: str) -> None:
        reply = QMessageBox.question(
            self,
            t("remove_live_feed"),
            t("confirm_remove_live_feed"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._fetcher.stop(layer_id)
        self._canvas.clear_live_positions(layer_id)
        self._live_trails.pop(layer_id, None)
        self._project.live_layers = [
            l for l in self._project.live_layers if l.id != layer_id
        ]
        self._project.mark_modified()
        self._live_panel.clear_layer(layer_id)

    def _cmd_manage_live_feeds(self) -> None:
        """Focus the live feeds dock panel."""
        for dock in self.findChildren(QDockWidget):
            if dock.widget() is self._live_panel:
                dock.show()
                dock.raise_()
                break

    def _on_live_positions_updated(self, layer_id: str, positions: list) -> None:
        # Cap to live_max_markers (ordered by first arriving)
        max_m = self._prefs.live_max_markers
        if max_m > 0 and len(positions) > max_m:
            positions = positions[:max_m]

        # Accumulate trail history keyed by label (or index for unlabelled markers)
        layer = next(
            (l for l in self._project.live_layers if l.id == layer_id), None
        )
        trail_len = getattr(layer, "trail_length", 0) if layer else 0
        if trail_len > 0:
            layer_trails = self._live_trails.setdefault(layer_id, {})
            for i, pos in enumerate(positions):
                marker_key = pos.get("label") or str(i)
                dq = layer_trails.setdefault(
                    marker_key, collections.deque(maxlen=trail_len)
                )
                dq.append({"lat": pos["lat"], "lon": pos["lon"]})
                pos["_trail"] = list(dq)

        self._canvas.update_live_positions(layer_id, positions)
        self._live_panel.set_status(layer_id, "live")
        self._live_panel.set_count(layer_id, len(positions))

    def _on_live_fetch_error(self, layer_id: str, error_msg: str) -> None:
        self._live_panel.set_status(layer_id, "error")
        if self._prefs.live_show_error_badge:
            self._status_bar.showMessage(
                f"[Live Feed] {error_msg}", 6000
            )

    # ── Data source commands ───────────────────────────────────────────────────

    def _cmd_ogc_browser(self) -> None:
        from bimap.ui.dialogs.ogc_browser_dialog import OgcBrowserDialog
        from bimap.ui.dialogs.data_source_dialog import DataSourceDialog as _DSD
        from bimap.models.data_source import DataSource, SourceType

        def _on_add_wfs(url: str, type_name: str) -> None:
            """Pre-fill DataSourceDialog with the discovered WFS URL."""
            ds = DataSource(
                name=url.split("/")[-1] or "WFS Layer",
                source_type=SourceType.WFS,
                connection={"url": url, "type_name": type_name, "max_features": "500"},
            )
            dlg2 = _DSD(ds, parent=self)
            if dlg2.exec() == dlg2.DialogCode.Accepted:
                self._add_data_source_from_model(dlg2.source)

        dlg = OgcBrowserDialog(on_add_wfs=_on_add_wfs, parent=self)
        dlg.exec()

    def _cmd_import_source_pack(self) -> None:
        from bimap.ui.dialogs.source_pack_dialog import SourcePackImportDialog
        dlg = SourcePackImportDialog(
            on_add_source=self._add_data_source_from_model,
            parent=self,
        )
        dlg.exec()

    def _cmd_export_source_pack(self) -> None:
        from bimap.ui.dialogs.source_pack_dialog import SourcePackExportDialog
        if not self._project.data_sources:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                t("No Sources"),
                t("Add at least one data source to the project before exporting a pack."),
            )
            return
        dlg = SourcePackExportDialog(list(self._project.data_sources), parent=self)
        dlg.exec()

    def _add_data_source_from_model(self, ds: "DataSource") -> None:
        """Shared helper used by _cmd_add_data_source and OGC browser."""
        try:
            connector = build_connector(ds)
            connector.connect()
        except (ValueError, NotImplementedError) as exc:
            ds.last_error = str(exc)
            connector = None
        # Grab geographic extent from the connector right after connect()
        if connector:
            ext = connector.get_extent()
            if ext:
                ds.extent = ext
        notify = lambda: (
            self._data_panel.refresh(self._project),
            self._source_label.setText(f"Sources: {len(self._project.data_sources)}"),
        )
        cmd = AddDataSourceCommand(
            self._project, ds, self._refresh_manager, connector, notify
        )
        self._undo_stack.push(cmd)
        # Auto-create a DataLayer display overlay for this source
        if not any(dl.source_id == str(ds.id) for dl in self._project.data_layers):
            from bimap.models.data_layer import DataLayer
            self._project.data_layers.append(
                DataLayer(name=ds.name, source_id=str(ds.id))
            )
            self._layers_panel.refresh(self._project)
        # Fly to extent immediately (even before data is fetched)
        if ds.extent:
            self._canvas.fit_to_extent(*ds.extent)
        # Auto-fetch immediately so WFS features appear right away
        self._refresh_manager.refresh_now(str(ds.id))

    def _cmd_add_data_source(self) -> None:
        dlg = DataSourceDialog(parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._add_data_source_from_model(dlg.source)

    def _cmd_add_wfs_source(self) -> None:
        """Open DataSourceDialog pre-set to WFS type."""
        from bimap.models.data_source import DataSource, SourceType
        ds = DataSource(source_type=SourceType.WFS)
        dlg = DataSourceDialog(ds, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._add_data_source_from_model(dlg.source)

    def _cmd_edit_data_source(self, source_id: str) -> None:
        ds = self._find_source(source_id)
        if not ds:
            return
        dlg = DataSourceDialog(copy.deepcopy(ds), parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            idx = next(i for i, s in enumerate(self._project.data_sources)
                       if str(s.id) == source_id)
            self._project.data_sources[idx] = dlg.source
            self._project.mark_modified()
            self._data_panel.refresh(self._project)

    def _cmd_remove_data_source(self, source_id: str) -> None:
        notify = lambda: (
            self._data_panel.refresh(self._project),
            self._source_label.setText(f"Sources: {len(self._project.data_sources)}"),
        )
        cmd = RemoveDataSourceCommand(
            self._project, source_id, self._refresh_manager, notify
        )
        self._undo_stack.push(cmd)

    def _cmd_refresh_all_sources(self) -> None:
        for ds in self._project.data_sources:
            if ds.enabled:
                self._refresh_manager.refresh_now(str(ds.id))

    def _cmd_extension_library(self) -> None:
        """Open the Extension Library manager dialog for the current project."""
        from bimap.ui.dialogs.extension_manager_dialog import ExtensionManagerDialog
        dlg = ExtensionManagerDialog(
            library=list(getattr(self._project, "extension_library", [])),
            parent=self,
        )
        if dlg.exec():
            self._project.extension_library = dlg.library
            self._project.mark_modified()
            # Refresh the properties panel so newly added templates appear
            # immediately in the "Set/Edit Extension" picker
            if self._selected:
                etype, eid = self._selected
                element = self._find_element(etype, eid)
                if element:
                    self._props_panel.show_element(element, etype)

    def _cmd_form_designer(self) -> None:
        """Open the Form Designer dialog."""
        from bimap.ui.dialogs.form_designer_dialog import FormDesignerDialog
        dlg = FormDesignerDialog(
            designs=list(getattr(self._project, "form_designs", [])),
            parent=self,
        )
        if dlg.exec():
            self._project.form_designs = dlg.designs
            self._project.mark_modified()
            # Refresh properties panel regardless of whether an element is selected,
            # so the Form picker combo updates immediately after creating new forms.
            if self._selected:
                etype, eid = self._selected
                element = self._find_element(etype, eid)
                if element:
                    self._props_panel.show_element(element, etype)
            else:
                # Panel is showing an element that isn't tracked as _selected
                self._props_panel.refresh_current()

    def _cmd_about(self) -> None:
        self._about_click_count += 1
        self._about_click_timer.start()
        if self._about_click_count >= 3:
            self._about_click_count = 0
            self._about_click_timer.stop()
            from bimap.ui.dialogs.debug_log_dialog import DebugLogDialog
            DebugLogDialog(self).exec()
            return
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h2>{APP_NAME} v{APP_VERSION}</h2>"
            "<p>Business Intelligence Map Designer</p>"
            "<p>Open Source Based: Python, PyQt6 and OpenStreetMap.</p>"
            "<p>Developed with love by OGRGijón for the community.</p>",
        )

    def _cmd_set_language(self, lang: str) -> None:
        if lang == get_language():
            return
        self._settings.setValue("language", lang)
        QMessageBox.information(
            self,
            t("Restart required"),
            t("Language changed. Please restart BIMAP to apply."),
        )

    def _cmd_preferences(self) -> None:
        from bimap.ui.dialogs.preferences_dialog import PreferencesDialog
        dlg = PreferencesDialog(self._prefs, self)
        if dlg.exec():
            self._apply_settings(dlg.get_settings())

    def _apply_settings(self, new_prefs: Settings) -> None:
        """Live-apply changed preferences without requiring a restart."""
        old = self._prefs
        self._prefs = new_prefs
        save_user_settings(new_prefs)
        set_icon_font_family(new_prefs.keypoint_icon_font_family)

        # Autosave interval
        self._autosave_timer.setInterval(new_prefs.autosave_interval_ms)

        # Undo stack limit
        self._undo_stack.setUndoLimit(new_prefs.undo_stack_limit)

        # Tile provider
        if new_prefs.tile_provider != old.tile_provider:
            self._canvas.set_tile_provider(new_prefs.tile_provider)
            self._project.map_state.tile_provider = new_prefs.tile_provider

        # Scale bar / north arrow (preserve current grid state when saving other prefs)
        self._canvas.set_overlay_flags(
            new_prefs.show_scale_bar, new_prefs.show_north_arrow,
            show_grid=self._canvas._show_grid,
        )
        self._canvas.set_grid_scale(new_prefs.grid_scale)

        # Live feed network timeout
        self._fetcher.set_timeout(new_prefs.live_network_timeout_s * 1000)

        # Language — requires restart
        if new_prefs.language != old.language:
            set_language(new_prefs.language)
            QMessageBox.information(
                self,
                t("Restart required"),
                t("Language changed. Please restart BIMAP to apply."),
            )

    def _cmd_set_delimitation(self) -> None:
        current = getattr(self._project.map_state, "delimitation_name", "")
        dlg = DelimitationDialog(current_name=current, parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        if dlg.clear_mode:
            self._cmd_clear_delimitation()
            return
        result = dlg.result_item
        if not result:
            return
        poly = result.polygon if result.polygon else result.bbox_polygon()
        self._project.map_state.delimitation_name = result.name
        self._project.map_state.delimitation_polygon = poly
        self._project.mark_modified()
        self._canvas.set_viewport(result.lat, result.lon, self._canvas.zoom)
        self._canvas.update()
        self.statusBar().showMessage(f"Delimitation set: {result.name}", 4000)

    def _cmd_clear_delimitation(self) -> None:
        self._project.map_state.delimitation_polygon = None
        self._project.map_state.delimitation_name = ""
        self._project.mark_modified()
        self._canvas.update()
        self.statusBar().showMessage(t("Delimitation cleared."), 3000)

    def _cmd_goto_coords(self) -> None:
        """Open the Place by Coordinates dialog and create a keypoint or polygon zone."""
        from bimap.ui.dialogs.goto_coords_dialog import GotoCoordsDialog
        dlg = GotoCoordsDialog(self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        mode = dlg.result_mode()
        coords = dlg.result_coords()
        if not coords:
            return

        if mode == "keypoint":
            lat, lon = coords[0]
            kp = Keypoint(lat=lat, lon=lon)
            cmd = AddKeypointCommand(self._project, kp, self._notify_canvas)
            self._undo_stack.push(cmd)
            self._project.mark_modified()
            self._canvas.set_viewport(lat, lon, self._canvas.zoom)
        else:
            zone = Zone(
                zone_type=ZoneType.POLYGON,
                coordinates=[LatLon(lat=lat, lon=lon) for lat, lon in coords],
            )
            cmd = AddZoneCommand(self._project, zone, self._notify_canvas)
            self._undo_stack.push(cmd)
            self._project.mark_modified()
            # Navigate to centroid
            clat = sum(c[0] for c in coords) / len(coords)
            clon = sum(c[1] for c in coords) / len(coords)
            self._canvas.set_viewport(clat, clon, self._canvas.zoom)

    def _cmd_work_offline(self) -> None:
        """Open the offline map tile downloader dialog."""
        from bimap.ui.dialogs.offline_map_dialog import OfflineMapDialog
        OfflineMapDialog(self._canvas, self).exec()

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _on_tool_selected(self, mode: str) -> None:
        self._canvas.set_tool(ToolMode(mode))

    def _on_provider_changed(self, key: str) -> None:
        self._canvas.set_tile_provider(key)
        self._project.map_state.tile_provider = key

    def _on_viewport_changed(self, lat: float, lon: float, zoom: int) -> None:
        self._project.map_state.center_lat = lat
        self._project.map_state.center_lon = lon
        self._project.map_state.zoom = zoom
        self._zoom_label.setText(f"Zoom: {zoom}")
        # Re-fetch viewport-tracked WFS sources after pan/zoom settles
        self._wfs_viewport_debounce.start()

    def _on_wfs_viewport_refresh(self) -> None:
        """Re-fetch WFS sources that have viewport_bbox=true with the current viewport as bbox."""
        from bimap.data.wfs_source import WfsSource
        from bimap.engine.tile_math import pixel_to_lat_lon
        from bimap.models.data_source import SourceType

        w, h = self._canvas.width(), self._canvas.height()
        if w <= 0 or h <= 0:
            return
        clat = self._canvas.center_lat
        clon = self._canvas.center_lon
        zoom = self._canvas.zoom
        lat_tl, lon_tl = pixel_to_lat_lon(0, 0, clat, clon, zoom, w, h)
        lat_br, lon_br = pixel_to_lat_lon(w, h, clat, clon, zoom, w, h)
        min_lat = min(lat_tl, lat_br)
        max_lat = max(lat_tl, lat_br)
        min_lon = min(lon_tl, lon_br)
        max_lon = max(lon_tl, lon_br)
        bbox_str = f"{min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}"

        for ds in getattr(self._project, "data_sources", []):
            if ds.source_type != SourceType.WFS:
                continue
            if ds.connection.get("viewport_bbox") != "true":
                continue
            connector = WfsSource(
                url=ds.connection.get("url", ""),
                type_name=ds.connection.get("type_name", ""),
                max_features=int(ds.connection.get("max_features", 500) or 500),
                bbox=bbox_str,
                cql_filter=ds.connection.get("cql_filter", ""),
            )
            self._refresh_manager.update_connector(str(ds.id), connector)
            self._refresh_manager.refresh_now(str(ds.id))

    def _on_coords_changed(self, lat: float, lon: float) -> None:
        self._coord_label.setText(f"Lat: {lat:.5f}  Lon: {lon:.5f}")

    def _on_draw_finished(self, element_type: str, element: Any) -> None:
        if element_type == "keypoint":
            element.metadata.setdefault("lat", str(round(element.lat, 6)))
            element.metadata.setdefault("lon", str(round(element.lon, 6)))

        # Always persist dimension fields as hidden attributes (zone only)
        if element_type == "zone":
            _update_dimensions_attr(element)
            _update_zone_derived_attrs(element)
        elif element_type == "annotation":
            _update_dimension_attrs(element)
        # Persist coordinates as a hidden "geo-space" attribute AFTER potential
        # coordinate rebuild so the JSON reflects the final positions.
        _update_geo_space_attr(element)

        notify = self._refresh_all
        match element_type:
            case "zone":
                cmd = AddZoneCommand(self._project, element, notify)
            case "keypoint":
                cmd = AddKeypointCommand(self._project, element, notify)
            case "annotation":
                cmd = AddAnnotationCommand(self._project, element, notify)
            case _:
                return
        self._undo_stack.push(cmd)
        # Auto-select newly created element
        self._on_element_selected(element_type, str(element.id))

    def _on_element_selected(self, element_type: str, element_id: str) -> None:
        if not element_type or not element_id:
            self._selected = None
            self._props_panel.clear()
            self._canvas.select_element("", "")
            self._layers_panel.select_element("", "")
            return
        self._selected = (element_type, element_id)
        element = self._find_element(element_type, element_id)
        if element:
            self._props_panel.show_element(element, element_type)
            self._props_dock.raise_()
        self._layers_panel.select_element(element_type, element_id)
        self._canvas.select_element(element_type, element_id)

    def _on_data_feature_selected(self, source_id: str, row_index: int) -> None:
        """Display attributes of a selected data feature (WFS/CSV/etc.)."""
        # Fetch the row data
        rows = self._canvas._data_layer_rows.get(source_id, [])
        if row_index < 0 or row_index >= len(rows):
            return
        row_data = dict(rows[row_index])
        
        # Find the data source name
        ds = next((s for s in self._project.data_sources if str(s.id) == source_id), None)
        if ds:
            row_data["_source_name"] = ds.name
        else:
            row_data["_source_name"] = source_id
        
        # Show in properties panel
        self._props_panel.show_element(row_data, "data_feature")
        self._props_dock.raise_()

    def _on_preset_applied(self, element_type: str, element_id: str, preset_name: str) -> None:
        """Apply a named style preset to the selected zone in one undoable step."""
        if element_type != "zone":
            return
        zone = self._find_element("zone", element_id)
        if not zone:
            return
        preset = next((p for p in self._project.style_presets if p.name == preset_name), None)
        if not preset:
            return
        old = copy.deepcopy(zone)
        zone.style = copy.deepcopy(preset.zone_style)
        zone.label.style = copy.deepcopy(preset.label_style)
        new = copy.deepcopy(zone)
        self._undo_stack.push(EditZoneCommand(self._project, old, new, self._notify_canvas))
        self._project.mark_modified()

    def _on_metadata_hidden_changed(self, element_type: str, element_id: str, hidden: list) -> None:
        element = self._find_element(element_type, element_id)
        if element and hasattr(element, "metadata_hidden"):
            element.metadata_hidden = hidden
            self._project.mark_modified()

    def _on_metadata_binding_changed(self, element_type: str, element_id: str,
                                      key: str, binding: object) -> None:
        element = self._find_element(element_type, element_id)
        if element and hasattr(element, "metadata_bindings"):
            if binding is None:
                element.metadata_bindings.pop(key, None)
            else:
                element.metadata_bindings[key] = binding
            self._project.mark_modified()

    def _on_metadata_changed(self, element_type: str, element_id: str,
                              key: str, value: object) -> None:
        """Push a SetMetadataCommand for any key-value edit from the properties panel."""
        cmd = SetMetadataCommand(
            self._project, element_type, element_id,
            key, value if value is not None else None, self._notify_canvas
        )
        self._undo_stack.push(cmd)

    def _on_visibility_changed(self, element_type: str, element_id: str, visible: bool) -> None:
        element = self._find_element(element_type, element_id)
        if element and hasattr(element, "visible"):
            element.visible = visible
            self._project.mark_modified()
            self._canvas.update()

    def _on_data_layer_visibility_changed(self, layer_id: str, visible: bool) -> None:
        """Toggle visibility of a data layer overlay."""
        for dl in self._project.data_layers:
            if dl.id == layer_id:
                dl.visible = visible
                break
        self._canvas.update()

    def _on_data_layer_opacity_changed(self, layer_id: str, opacity: float) -> None:
        """Update opacity of a data layer overlay."""
        for dl in self._project.data_layers:
            if dl.id == layer_id:
                dl.opacity = opacity
                break
        self._canvas.update()

    def _on_layer_visibility_changed(self, layer_name: str, visible: bool) -> None:
        """Toggle visibility of a layer and all its elements."""
        for layer in self._project.layers:
            if layer.name == layer_name:
                layer.visible = visible
                break
        for elem in (*self._project.zones, *self._project.keypoints, *self._project.annotations):
            if getattr(elem, "layer", "Default") == layer_name:
                elem.visible = visible
        self._project.mark_modified()
        self._canvas.update()
        self._layers_panel.refresh(self._project)

    def _on_layer_add_requested(self) -> None:
        name, ok = QInputDialog.getText(self, t("Add Layer"), t("Layer name:"))
        if not ok or not name.strip():
            return
        name = name.strip()
        if any(lyr.name == name for lyr in self._project.layers):
            QMessageBox.warning(self, t("Duplicate Layer"), t("A layer named '{name}' already exists.").format(name=name))
            return
        from bimap.models.layer import Layer
        self._project.layers.append(Layer(name=name))
        self._project.mark_modified()
        self._layers_panel.refresh(self._project)

    def _on_layer_remove_requested(self, layer_name: str) -> None:
        """Move all elements from *layer_name* to Default, then remove the layer."""
        for elem in (*self._project.zones, *self._project.keypoints, *self._project.annotations):
            if getattr(elem, "layer", "Default") == layer_name:
                elem.layer = "Default"
        self._project.layers = [lyr for lyr in self._project.layers if lyr.name != layer_name]
        self._project.mark_modified()
        self._layers_panel.refresh(self._project)
        self._canvas.update()

    def _on_property_changed(self, etype: str, eid: str, field: str, value: Any) -> None:
        """Apply a property edit to the element model."""
        try:
            self._apply_property_change(etype, eid, field, value)
        except Exception as exc:  # noqa: BLE001
            import logging as _logging
            _logging.getLogger(__name__).error(
                "Property change failed: %s.%s = %r — %s", etype, field, value, exc,
                exc_info=True,
            )

    def _apply_property_change(self, etype: str, eid: str, field: str, value: Any) -> None:
        """Internal: apply a validated property edit and push an undo command."""
        element = self._find_element(etype, eid)
        if not element:
            return
        old = copy.deepcopy(element)
        try:
            _set_nested_attr(element, field, value)
        except (AttributeError, ValueError):
            return
        # When svg_fill_url changes: sync to hidden metadata attribute "__svg_background"
        if field == "svg_fill_url" and etype == "zone":
            _sync_svg_background_attr(element, str(value))
        # When geometry fields change: refresh hidden width_m / height_m / rotation_deg / radius_m attrs
        if field in ("width_m", "height_m", "rotation_deg") and etype == "zone":
            _update_dimensions_attr(element)
        # Rebuild derived attrs (area, perimeter, vertices, centroid) for any
        # spatial or geometry change on a zone.
        if etype == "zone" and field in (
            "width_m", "height_m", "radius_m", "rotation_deg", "coordinates",
        ):
            _update_zone_derived_attrs(element)
        # Persist geo-space AFTER potential coordinate rebuild (keeps extension
        # HTML in sync with the final vertex positions).
        if field in ("radius_m", "width_m", "height_m", "lat", "lon", "rotation_deg", "coordinates"):
            _update_geo_space_attr(element)
        new = copy.deepcopy(element)
        # Push edit command
        if etype == "zone":
            cmd = EditZoneCommand(self._project, old, new, self._notify_canvas)
        elif etype == "keypoint":
            cmd = EditKeypointCommand(self._project, old, new, self._notify_canvas)
        elif etype == "annotation":
            cmd = EditAnnotationCommand(self._project, old, new, self._notify_canvas)
        else:
            return
        self._undo_stack.push(cmd)

    def _on_data_refreshed(self, source_id: str, rows: list) -> None:
        is_first_load = source_id not in self._canvas._data_layer_rows
        # Apply field mappings and update runtime state
        for ds in self._project.data_sources:
            if str(ds.id) == source_id:
                self._apply_mappings(ds, rows)
                ds.last_refresh = str(__import__("datetime").datetime.now().isoformat())
                ds.last_error = ""
                ds.connection_state = "ok"
                break
        # Apply metadata key bindings
        self._apply_metadata_bindings(source_id, rows)
        self._data_panel.update_source_status(source_id, "")
        self._canvas.update_data_layer_rows(source_id, rows)
        # Auto-fly to data on first load if there are coordinates
        if is_first_load:
            self._fit_canvas_to_source(source_id, rows)

    def _fit_canvas_to_rows(self, rows: list) -> None:
        """Fit the canvas viewport to the bounding box of geo-coded rows."""
        lats, lons = [], []
        for r in rows:
            try:
                if r.get("_lat") and r.get("_lon"):
                    lats.append(float(r["_lat"]))
                    lons.append(float(r["_lon"]))
            except (ValueError, TypeError):
                pass
        if not lats:
            return
        self._canvas.fit_to_extent(
            min(lats), min(lons), max(lats), max(lons)
        )

    def _fit_canvas_to_source(self, source_id: str, rows: list) -> None:
        """Fit to stored extent first, then fall back to row coordinates."""
        for ds in self._project.data_sources:
            if str(ds.id) == source_id and ds.extent:
                self._canvas.fit_to_extent(*ds.extent)
                return
        self._fit_canvas_to_rows(rows)

    def _on_fit_data_source(self, source_id: str) -> None:
        """Fly to the data extent for a specific source."""
        # Update extent from rows if already loaded
        rows = self._canvas._data_layer_rows.get(source_id, [])
        if rows:
            self._fit_canvas_to_source(source_id, rows)
        else:
            # Try stored extent first (from GetCapabilities), else trigger refresh
            ds = next((d for d in self._project.data_sources if str(d.id) == source_id), None)
            if ds and ds.extent:
                self._canvas.fit_to_extent(*ds.extent)
            else:
                # No data yet — trigger a refresh first, fly will happen on arrival
                self._refresh_manager.refresh_now(source_id)

    def _on_refresh_started(self, source_id: str) -> None:
        """Called when a background refresh begins — update UI to 'connecting' state."""
        for ds in self._project.data_sources:
            if str(ds.id) == source_id:
                ds.connection_state = "connecting"
                break
        self._data_panel.set_connecting(source_id)
        self.statusBar().showMessage(
            t("Refreshing data source…"), 0
        )

    def _on_refresh_stats(self, source_id: str, row_count: int, ms: int) -> None:
        """Store performance stats and push to the data panel."""
        for ds in self._project.data_sources:
            if str(ds.id) == source_id:
                ds.row_count = row_count
                ds.last_refresh_ms = ms
                break
        self._data_panel.set_refreshed(source_id, row_count, ms)
        self.statusBar().showMessage(
            t("{n} rows loaded in {ms} ms").format(n=row_count, ms=ms), 4000
        )

    def _apply_metadata_bindings(self, source_id: str, rows: list) -> None:
        """Update bound metadata keys on all zones and keypoints for the refreshed source."""
        elements = [*self._project.zones, *self._project.keypoints]
        for element in elements:
            bindings = getattr(element, "metadata_bindings", {})
            if not bindings:
                continue
            for key, b in bindings.items():
                if getattr(b, "source_id", "") != source_id:
                    continue
                column = getattr(b, "column", "")
                match_field = getattr(b, "match_field", "")
                match_value = getattr(b, "match_value", "{{element.name}}")
                aggregate = getattr(b, "aggregate", "first")
                # Resolve template placeholders
                resolved = (
                    match_value
                    .replace("{{element.name}}", getattr(element, "name", ""))
                    .replace("{{element.id}}", str(element.id))
                )
                if match_field:
                    matching = [r for r in rows if str(r.get(match_field, "")) == resolved]
                else:
                    matching = rows
                if not matching:
                    continue
                try:
                    if aggregate == "first":
                        value = str(matching[0].get(column, ""))
                    elif aggregate == "last":
                        value = str(matching[-1].get(column, ""))
                    elif aggregate == "count":
                        value = str(len(matching))
                    elif aggregate in ("sum", "avg"):
                        vals = [float(r.get(column, 0)) for r in matching
                                if r.get(column) not in (None, "")]
                        if vals:
                            value = str(sum(vals) if aggregate == "sum"
                                        else sum(vals) / len(vals))
                        else:
                            continue
                    else:
                        value = str(matching[0].get(column, ""))
                    element.metadata[key] = value
                except (TypeError, ValueError):
                    pass
        if elements:
            self._project.mark_modified()

    def _on_refresh_error(self, source_id: str, message: str) -> None:
        for ds in self._project.data_sources:
            if str(ds.id) == source_id:
                ds.last_error = message
                ds.connection_state = "error"
                break
        self._data_panel.update_source_status(source_id, message)
        self.statusBar().showMessage(f"Data refresh error: {message}", 6000)

    def _on_context_action(self, action: str, etype: str, eid: str) -> None:
        """Handle right-click context menu actions from the map canvas."""
        match action:
            case "remove":
                name = eid[:8]
                element = self._find_element(etype, eid)
                if element and hasattr(element, "name"):
                    name = element.name
                elif etype == "annotation" and element:
                    name = next(
                        (line.strip() for line in element.content.splitlines() if line.strip()),
                        "Dimension" if element.ann_type.value == "dimension" else "Annotation",
                    )
                reply = QMessageBox.question(
                    self,
                    t("Confirm Remove"),
                    t("Remove '{name}'?").format(name=name),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._delete_element(etype, eid)
            case "edit":
                self._on_element_selected(etype, eid)
                self._props_dock.show()
                self._props_dock.raise_()
            case "move":
                self._canvas.set_tool(ToolMode.MOVE_ELEMENT)
                self._canvas._interaction.start_move_element(etype, eid)
            case "view_metadata":
                element = self._find_element(etype, eid)
                if element:
                    name = getattr(element, "name", None) or getattr(
                        element, "info_card", None
                    ) and element.info_card.title or eid[:8]
                    metadata = getattr(element, "metadata", {})
                    dlg = MetadataViewDialog(name, etype, metadata, self)
                    dlg.exec()
            case "open_extension":
                self._open_ext_viewer(etype, eid)
            case "edit_info":
                element = self._find_element(etype, eid)
                if element and hasattr(self._project, "form_designs"):
                    applicable = [
                        fd for fd in self._project.form_designs
                        if fd.target in ("both", etype)
                    ]
                    if not applicable:
                        return
                    chosen_form = applicable[0]
                    if len(applicable) > 1:
                        names = [fd.name for fd in applicable]
                        name, ok = QInputDialog.getItem(
                            self, t("Edit Info"), t("Select form:"), names, 0, False
                        )
                        if not ok:
                            return
                        chosen_form = next(fd for fd in applicable if fd.name == name)
                    from bimap.ui.dialogs.form_fill_dialog import FormFillDialog
                    def _live(el: Any, key: str, val: str, _etype=etype) -> None:
                        cmd = SetMetadataCommand(
                            self._project, _etype, str(el.id), key, val, self._notify_canvas
                        )
                        self._undo_stack.push(cmd)

                    dlg = FormFillDialog(chosen_form, element, etype, self, on_change=_live)
                    if dlg.exec():
                        self._project.mark_modified()
                        self._props_panel.refresh_current()

    def _on_open_extension(self, etype: str, eid: str) -> None:
        """Handle double-click open-extension from canvas."""
        self._open_ext_viewer(etype, eid)

    def _on_multi_select(self, items: list) -> None:
        """Handle magic-wand lasso — offer batch delete and/or polygon creation."""
        n = len(items)
        lasso_zone = getattr(self._canvas._interaction, "_lasso_zone", None)

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(t("Dynamic Zone"))
        if n > 0:
            msg_box.setText(t("{n} element(s) inside the Dynamic Zone.").format(n=n))
        else:
            msg_box.setText(t("No elements found inside Dynamic Zone."))

        btn_delete = None
        if n > 0:
            btn_delete = msg_box.addButton(
                t("🗑  Delete {n} element(s)").format(n=n),
                QMessageBox.ButtonRole.DestructiveRole,
            )
        btn_zone = msg_box.addButton(t("⬠  Create Polygon Zone"), QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton(QMessageBox.StandardButton.Cancel)
        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == btn_delete:
            cmd = RemoveMultipleCommand(self._project, items, self._refresh_all)
            self._undo_stack.push(cmd)
        elif clicked == btn_zone and lasso_zone is not None:
            cmd = AddZoneCommand(self._project, lasso_zone, self._refresh_all)
            self._undo_stack.push(cmd)
            self._on_element_selected("zone", str(lasso_zone.id))

    def _on_network_status_changed(self, is_online: bool) -> None:
        if is_online:
            self._net_label.setText("🌐 Online")
            self._net_label.setStyleSheet("")
            self._refresh_tiles_btn.setVisible(False)
        else:
            self._net_label.setText("📦 Offline")
            self._net_label.setStyleSheet("color: #ff8800; font-weight: bold;")
            self._refresh_tiles_btn.setVisible(True)

    def _on_element_rotated(self, etype: str, eid: str, degrees: float) -> None:
        """Apply a rotation edit pushed by the Rotate tool (one degree at a time)."""
        if etype != "zone":
            return
        zone = self._find_element("zone", eid)
        if not zone:
            return
        old = copy.deepcopy(zone)
        zone.rotation_deg = degrees % 360.0
        _update_dimensions_attr(zone)
        _update_zone_derived_attrs(zone)
        new = copy.deepcopy(zone)
        self._undo_stack.push(EditZoneCommand(self._project, old, new, self._notify_canvas))
        # Sync the toolbar spinbox with the arrow-key driven angle
        self._toolbar.set_rotate_angle(degrees)

    def _on_rotate_degree_from_toolbar(self, degrees: float) -> None:
        """Handle direct degree entry from the toolbar spinbox (debounced undo)."""
        handler = self._canvas._interaction
        if handler._rotate_element_type and handler._rotate_element_id:
            handler._rotate_current_deg = degrees % 360.0
            handler.request_repaint.emit()          # update visor immediately
            self._rotate_spinbox_timer.start()      # restart debounce window

    def _commit_rotate_from_spinbox(self) -> None:
        """Called by debounce timer: push one undo command for the final spinbox angle."""
        handler = self._canvas._interaction
        if handler._rotate_element_type and handler._rotate_element_id:
            handler.element_rotated.emit(
                handler._rotate_element_type,
                handler._rotate_element_id,
                handler._rotate_current_deg,
            )

    def _on_toggle_grid(self, enabled: bool) -> None:
        """Toggle the coordinate grid (precision-move overlay) on the map canvas."""
        flags = {
            "show_scale_bar": self._canvas._show_scale_bar,
            "show_north_arrow": self._canvas._show_north_arrow,
            "show_grid": enabled,
        }
        self._canvas.set_overlay_flags(**flags)

    def _on_element_move_dropped(self, etype: str, eid: str, lat: float, lon: float) -> None:
        """Push a MoveElementCommand when the user drops an element at the new position."""
        cmd = MoveElementCommand(self._project, etype, eid, lat, lon, self._refresh_all)
        self._undo_stack.push(cmd)
        # Keep geo-space and derived attrs current after the move
        element = self._find_element(etype, eid)
        if element:
            _update_geo_space_attr(element)
            if etype == "zone":
                _update_zone_derived_attrs(element)
            elif etype == "annotation":
                _update_dimension_attrs(element)
            self._project.mark_modified()

    def _on_add_annotation_at(self, ann_type: str, lat: float, lon: float) -> None:
        """Create a text annotation at the right-clicked map position."""
        from bimap.models.annotation import Annotation, AnnotationType, CanvasPosition
        px = self._canvas.lat_lon_to_px(lat, lon)
        ann = Annotation(
            ann_type=AnnotationType.TEXT_BOX,
            anchor_lat=lat,
            anchor_lon=lon,
            content="Text",
        )
        ann.position = CanvasPosition(x=px.x(), y=px.y(), width=120, height=40)
        cmd = AddAnnotationCommand(self._project, ann, self._refresh_all)
        self._undo_stack.push(cmd)
        self._on_element_selected("annotation", str(ann.id))

    def _on_layer_element_action(self, action: str, etype: str, eid: str) -> None:
        """Handle element actions triggered from the layers panel context menu."""
        match action:
            case "go_to":
                element = self._find_element(etype, eid)
                if element is None:
                    return
                lat = getattr(element, "lat", None)
                lon = getattr(element, "lon", None)
                if lat is None and hasattr(element, "coordinates") and element.coordinates:
                    lat = element.coordinates[0].lat
                    lon = element.coordinates[0].lon
                if lat is not None and lon is not None:
                    self._canvas.set_viewport(lat, lon, self._project.map_state.zoom)
            case "edit" | "remove":
                self._on_context_action(action, etype, eid)
            case "update":
                element = self._find_element(etype, eid)
                if element and getattr(element, "data_binding", None):
                    self._refresh_manager.refresh_now(str(element.data_binding.source_id))

    def _on_element_layer_changed(self, etype: str, eid: str, new_layer: str) -> None:
        """Move an element to a different layer after drag-drop in the layers panel."""
        element = self._find_element(etype, eid)
        if element:
            element.layer = new_layer
            # Keep hidden metadata attrs in sync with the new layer value.
            if etype == "zone":
                _update_zone_derived_attrs(element)
            self._project.mark_modified()
            self._layers_panel.refresh(self._project)
            self._canvas.update()

    # ── Element helpers ────────────────────────────────────────────────────────

    def _find_element(self, element_type: str, element_id: str) -> Any | None:
        try:
            uid = UUID(element_id)
        except (ValueError, AttributeError):
            return None
        match element_type:
            case "zone":
                return next((z for z in self._project.zones if z.id == uid), None)
            case "keypoint":
                return next((k for k in self._project.keypoints if k.id == uid), None)
            case "annotation":
                return next((a for a in self._project.annotations if a.id == uid), None)
        return None

    def _find_source(self, source_id: str) -> DataSource | None:
        return next((s for s in self._project.data_sources if str(s.id) == source_id), None)

    def _delete_element(self, element_type: str, element_id: str) -> None:
        try:
            uid = UUID(element_id)
        except (ValueError, AttributeError):
            return
        notify = self._refresh_all
        match element_type:
            case "zone":
                cmd = RemoveZoneCommand(self._project, uid, notify)
            case "keypoint":
                cmd = RemoveKeypointCommand(self._project, uid, notify)
            case "annotation":
                cmd = RemoveAnnotationCommand(self._project, uid, notify)
            case _:
                return
        self._undo_stack.push(cmd)
        self._selected = None
        self._props_panel.clear()

    def _register_source(self, ds: DataSource) -> None:
        try:
            connector = build_connector(ds)
            connector.connect()
            self._refresh_manager.register(ds, connector)
            if ds.refresh_mode == RefreshMode.ON_OPEN:
                self._refresh_manager.refresh_now(str(ds.id))
        except ValueError as exc:
            ds.last_error = str(exc)

    def _apply_mappings(self, ds: DataSource, rows: list[dict]) -> None:
        """Apply field mappings from *rows* to project elements."""
        for mapping in ds.field_mappings:
            try:
                uid = UUID(mapping.target_element_id)
            except (ValueError, AttributeError):
                continue
            element = self._find_element(mapping.target_element_type, str(uid))
            if not element or not rows:
                continue
            raw_value = rows[0].get(mapping.source_column)
            if mapping.transform:
                try:
                    raw_value = _safe_eval_transform(mapping.transform, raw_value)
                except Exception:
                    pass
            try:
                _set_nested_attr(element, mapping.target_property, raw_value)
            except (AttributeError, ValueError):
                pass

    def _assign_keynote(self, kp_id: str) -> None:
        existing = {k.keynote_number for k in self._project.keypoints
                    if k.keynote_number is not None}
        next_num = 1
        while next_num in existing:
            next_num += 1
        kp = self._find_element("keypoint", kp_id)
        if kp:
            kp.keynote_number = next_num
            self._project.mark_modified()
            self._keynotes_panel.refresh(self._project)
            self._canvas.update()

    def _clear_keynote(self, kp_id: str) -> None:
        kp = self._find_element("keypoint", kp_id)
        if kp:
            kp.keynote_number = None
            self._project.mark_modified()
            self._keynotes_panel.refresh(self._project)
            self._canvas.update()

    def _confirm_discard(self) -> bool:
        if self._undo_stack.isClean():
            return True
        reply = ask_question(
            self,
            t("Unsaved Changes"),
            t("You have unsaved changes. Discard them?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
        else:
            self.shutdown()
            event.accept()

    def shutdown(self) -> None:
        """Stop background work before Python starts destroying Qt threads."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self._autosave_timer.stop()
        self._wfs_viewport_debounce.stop()
        self._rotate_spinbox_timer.stop()
        self._about_click_timer.stop()
        self._fetcher.stop_all()
        self._refresh_manager.shutdown()
        from bimap.ui.map_canvas.tile_fetcher import stop_all_tile_fetches
        stop_all_tile_fetches()


# ── Utility ────────────────────────────────────────────────────────────────────

def _hav_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres between two WGS-84 coordinate pairs."""
    R = 6_371_000.0
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(1.0, a)))


def _sync_svg_background_attr(element: Any, path: str) -> None:
    """Keep the hidden ``__svg_background`` metadata key in sync with ``svg_fill_url``.

    The key is added to ``metadata_hidden`` so it is invisible in the extension
    viewer (BIMAP_DATA.metadata) by default, but extension HTML can opt-in by
    un-hiding it if needed.
    """
    _KEY = "__svg_background"
    meta: dict = getattr(element, "metadata", {})
    hidden: list = list(getattr(element, "metadata_hidden", []))
    if path:
        meta[_KEY] = path
    else:
        meta.pop(_KEY, None)
    if _KEY not in hidden:
        hidden.append(_KEY)
    element.metadata = meta
    element.metadata_hidden = hidden


def _update_geo_space_attr(element: Any) -> None:
    """Persist element coordinates as a JSON string in the hidden ``geo-space`` attribute.

    Always keeps ``geo-space`` in ``metadata_hidden`` so it does not clutter
    the extension viewer, but extension HTML can access it via BIMAP_DATA if needed.
    """
    _KEY = "geo-space"
    meta: dict = dict(getattr(element, "metadata", {}))
    hidden: list = list(getattr(element, "metadata_hidden", []))
    # Build geo payload
    if hasattr(element, "coordinates"):
        coords = element.coordinates
        if coords:
            geo = [{
                "lat": round(c.lat, 7),
                "lon": round(c.lon, 7),
            } for c in coords]
            meta[_KEY] = json.dumps(geo, separators=(",", ":"))
        else:
            meta.pop(_KEY, None)
    elif hasattr(element, "lat") and hasattr(element, "lon"):
        meta[_KEY] = json.dumps(
            {"lat": round(element.lat, 7), "lon": round(element.lon, 7)},
            separators=(",", ":"),
        )
    else:
        return
    if _KEY not in hidden:
        hidden.append(_KEY)
    element.metadata = meta
    element.metadata_hidden = hidden


def _update_dimension_attrs(element: Any) -> None:
    """Store visible endpoints and formatted distance for a dimension annotation."""
    if getattr(element, "ann_type", None).value != "dimension":
        return
    values = (
        element.dimension_start_lat,
        element.dimension_start_lon,
        element.dimension_end_lat,
        element.dimension_end_lon,
    )
    if any(value is None for value in values):
        return
    distance = _haversine_m(
        element.dimension_start_lat,
        element.dimension_start_lon,
        element.dimension_end_lat,
        element.dimension_end_lon,
    )
    from_point = f"({element.dimension_start_lat:.7f}, {element.dimension_start_lon:.7f})"
    to_point = f"({element.dimension_end_lat:.7f}, {element.dimension_end_lon:.7f})"
    distance_text = _format_distance_m(distance)
    element.metadata.update({
        "from_point": from_point,
        "to_point": to_point,
        "from_lat": f"{element.dimension_start_lat:.7f}",
        "from_lon": f"{element.dimension_start_lon:.7f}",
        "to_lat": f"{element.dimension_end_lat:.7f}",
        "to_lon": f"{element.dimension_end_lon:.7f}",
        "dimension": distance_text,
        "distance": distance_text,
    })


def _update_dimensions_attr(element: Any) -> None:
    """Keep hidden metadata attributes ``width_m``, ``height_m``, and
    ``rotation_deg`` in sync with the corresponding model fields on zones.

    These are stored individually (not as JSON) so extension HTML can easily
    read them as plain numbers.  All three keys are added to
    ``metadata_hidden`` so they don't clutter the extension viewer.
    """
    _KEYS = ("width_m", "height_m", "rotation_deg")
    meta: dict = dict(getattr(element, "metadata", {}))
    hidden: list = list(getattr(element, "metadata_hidden", []))
    changed = False
    for key in _KEYS:
        val = getattr(element, key, None)
        if val is not None:
            meta[key] = str(round(float(val), 6))
            if key not in hidden:
                hidden.append(key)
            changed = True
    if changed:
        element.metadata = meta
        element.metadata_hidden = hidden


def _update_zone_derived_attrs(element: Any) -> None:
    """Recompute all geometry-derived attributes of a Zone and persist them
    as hidden metadata so extension HTML and data bindings can read them.

    Derived attrs written (all hidden):
        area_m2, perimeter_m, vertex_count, centroid_lat, centroid_lon

    For RECTANGLE zones with explicit width_m / height_m set, the
    ``coordinates`` list is rebuilt from the centroid + dimensions + rotation
    so that rendered vertices always match the numeric fields.
    """
    zone_type_str = str(getattr(element, "zone_type", ""))
    coords = list(getattr(element, "coordinates", []) or [])
    width_m: float = float(getattr(element, "width_m", 0) or 0)
    height_m: float = float(getattr(element, "height_m", 0) or 0)
    radius_m: float = float(getattr(element, "radius_m", 0) or 0)
    rotation_deg: float = float(getattr(element, "rotation_deg", 0) or 0)

    # ── 0. For RECTANGLE with missing dimensions, derive from vertices ───── #
    if zone_type_str == str(ZoneType.RECTANGLE) and len(coords) >= 4 and (width_m == 0 or height_m == 0):
        _w = _hav_m(coords[0].lat, coords[0].lon, coords[1].lat, coords[1].lon)
        _h = _hav_m(coords[1].lat, coords[1].lon, coords[2].lat, coords[2].lon)
        if width_m == 0 and _w > 0:
            element.width_m = _w
            width_m = _w
        if height_m == 0 and _h > 0:
            element.height_m = _h
            height_m = _h

    # ── 1. Rebuild rectangle coordinates from dimensions ─────────────────── #
    if zone_type_str == str(ZoneType.RECTANGLE) and width_m > 0 and height_m > 0 and coords:
        # Centroid of existing vertices
        c_lat = sum(c.lat for c in coords) / len(coords)
        c_lon = sum(c.lon for c in coords) / len(coords)
        # Angular half-extents
        hl = height_m / 2.0 / 111_320.0                                # Δlat
        wl = width_m  / 2.0 / (111_320.0 * math.cos(math.radians(c_lat)) + 1e-12)  # Δlon
        # Unrotated corners in (Δlat, Δlon) relative to centroid
        offsets = [
            ( hl, -wl),  # NW
            ( hl,  wl),  # NE
            (-hl,  wl),  # SE
            (-hl, -wl),  # SW
        ]
        # Apply rotation around centroid
        if rotation_deg != 0.0:
            rad = math.radians(rotation_deg)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            # Convert to equal-scale metres, rotate, convert back
            cos_lat = math.cos(math.radians(c_lat)) + 1e-12
            rotated = []
            for dlat, dlon in offsets:
                mx = dlon * cos_lat * 111_320.0   # local east metres
                my = dlat * 111_320.0              # local north metres
                rx = mx * cos_r - my * sin_r
                ry = mx * sin_r + my * cos_r
                rotated.append(LatLon(lat=c_lat + ry / 111_320.0,
                                      lon=c_lon + rx / (cos_lat * 111_320.0)))
            element.coordinates = rotated
            coords = rotated
        else:
            new_coords = [LatLon(lat=c_lat + dlat, lon=c_lon + dlon) for dlat, dlon in offsets]
            element.coordinates = new_coords
            coords = new_coords

    # ── 2. Compute centroid ───────────────────────────────────────────────── #
    if zone_type_str == str(ZoneType.CIRCLE) and coords:
        c_lat, c_lon = coords[0].lat, coords[0].lon
    elif coords:
        c_lat = sum(c.lat for c in coords) / len(coords)
        c_lon = sum(c.lon for c in coords) / len(coords)
    else:
        return  # nothing to compute

    # ── 3. Compute area ───────────────────────────────────────────────────── #
    if zone_type_str == str(ZoneType.CIRCLE):
        area_m2 = math.pi * radius_m ** 2
    elif len(coords) >= 3:
        R = 6_371_000.0
        n = len(coords)
        total = 0.0
        for i in range(n):
            lat1 = math.radians(coords[i].lat)
            lat2 = math.radians(coords[(i + 1) % n].lat)
            dlon = math.radians(coords[(i + 1) % n].lon - coords[i].lon)
            total += dlon * (2 + math.sin(lat1) + math.sin(lat2))
        area_m2 = abs(total) * R * R / 2.0
    else:
        area_m2 = 0.0

    # ── 4. Compute perimeter ──────────────────────────────────────────────── #
    if zone_type_str == str(ZoneType.CIRCLE):
        perimeter_m = 2 * math.pi * radius_m
    elif len(coords) >= 2:
        R = 6_371_000.0
        perimeter_m = 0.0
        n = len(coords)
        for i in range(n):
            c1, c2 = coords[i], coords[(i + 1) % n]
            φ1, φ2 = math.radians(c1.lat), math.radians(c2.lat)
            Δφ = math.radians(c2.lat - c1.lat)
            Δλ = math.radians(c2.lon - c1.lon)
            a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
            perimeter_m += 2 * R * math.asin(math.sqrt(min(1.0, a)))
    else:
        perimeter_m = 0.0

    # ── 5. Write hidden metadata ──────────────────────────────────────────── #
    _DERIVED = {
        "shape_type":   zone_type_str.split(".")[-1],          # "circle", "rectangle", "polygon"
        "area_m2":      f"{area_m2:.2f}",
        "perimeter_m":  f"{perimeter_m:.2f}",
        "vertex_count": str(len(coords)),
        "centroid_lat": f"{c_lat:.7f}",
        "centroid_lon": f"{c_lon:.7f}",
        "layer":        str(getattr(element, "layer", "Default") or "Default"),
    }
    if zone_type_str == str(ZoneType.CIRCLE):
        _DERIVED["radius_m"] = f"{radius_m:.2f}"
    meta: dict = dict(getattr(element, "metadata", {}))
    hidden: list = list(getattr(element, "metadata_hidden", []))
    for key, val in _DERIVED.items():
        meta[key] = val
        if key not in hidden:
            hidden.append(key)
    element.metadata = meta
    element.metadata_hidden = hidden
    # Dimension fields may have been derived from the current vertices above;
    # sync them after that derivation so width_m/height_m are persisted too.
    _update_dimensions_attr(element)
