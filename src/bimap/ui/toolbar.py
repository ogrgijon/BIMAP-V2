"""Toolbar components: VS Code-style vertical ActivityBar + slim top SearchBar."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QWidget,
)

from bimap.config import TILE_PROVIDERS
from bimap.i18n import t
from bimap.ui._utils import create_help_button, show_help_dialog
from bimap.ui.map_canvas.interaction import ToolMode

# ── Stylesheets ──────────────────────────────────────────────────────────────

_TOOLBAR_QSS = """
QToolBar {
    background: #3A3A3C;
    border: none;
    border-bottom: 1px solid #505050;
    spacing: 2px;
    padding: 2px 6px;
}
QToolBar::separator {
    width: 1px;
    background: #505050;
    margin: 4px 3px;
}
QToolButton {
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    color: #C8C8C8;
    font-size: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    padding: 0px;
    margin: 0px;
    text-align: center;
}
QToolButton:hover {
    color: #FFFFFF;
    background: #4A4A4E;
}
QToolButton:checked {
    color: #FFFFFF;
    border-bottom: 3px solid #007ACC;
    background: rgba(0, 122, 204, 0.20);
}
QToolButton:pressed {
    background: #094771;
    color: #FFFFFF;
}
"""

_SEARCH_BAR_QSS = """
QToolBar {
    background: #2D2D2D;
    border-bottom: 1px solid #3C3C3C;
    spacing: 4px;
    padding: 3px 8px;
}
QToolButton {
    background: #3C3C3C;
    border: 1px solid #555555;
    color: #D4D4D4;
    border-radius: 3px;
    padding: 2px 8px;
    font-size: 11px;
}
QToolButton:hover {
    background: #4A4A4A;
    border-color: #007ACC;
}
"""

# ── SearchBar ────────────────────────────────────────────────────────────────


class SearchBar(QToolBar):
    """
    Slim top toolbar containing:
      • Geocoder search input + Search button
      • Tile provider selector
      • Zoom in / Zoom out

    Signals
    -------
    search_requested(str)
    tile_provider_changed(str)
    zoom_in_requested()
    zoom_out_requested()
    """

    search_requested = pyqtSignal(str)
    tile_provider_changed = pyqtSignal(str)
    zoom_in_requested = pyqtSignal()
    zoom_out_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Search & Map Controls", parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setStyleSheet(_SEARCH_BAR_QSS)

        # ── Geocoder ──────────────────────────────────────────────────────── #
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("🔍  " + t("Search location…"))
        self._search_edit.setMinimumWidth(240)
        self._search_edit.setMaximumWidth(400)
        self._search_edit.setStyleSheet(
            "font-size: 12px; padding: 4px 8px;"
            "background:#3C3C3C; color:#D4D4D4;"
            "border:1px solid #555; border-radius:3px;"
        )
        self._search_edit.returnPressed.connect(self._emit_search)
        self.addWidget(self._search_edit)

        btn_search = QToolButton(self)
        btn_search.setText(t("Search"))
        btn_search.setToolTip(t("Search location (Enter)"))
        btn_search.clicked.connect(self._emit_search)
        self.addWidget(btn_search)

        self.addSeparator()

        # ── Tile provider ─────────────────────────────────────────────────── #
        self.addWidget(QLabel(t("  Map: ")))
        self._provider_combo = QComboBox()
        self._provider_combo.setToolTip(t("Tile provider"))
        self._provider_combo.setStyleSheet(
            "background:#3C3C3C; color:#D4D4D4;"
            "border:1px solid #555; border-radius:3px; padding:2px 6px;"
        )
        for key, info in TILE_PROVIDERS.items():
            self._provider_combo.addItem(info["label"], key)
        self._provider_combo.currentIndexChanged.connect(
            lambda: self.tile_provider_changed.emit(self._provider_combo.currentData())
        )
        self.addWidget(self._provider_combo)

        self.addSeparator()

        # ── Zoom ──────────────────────────────────────────────────────────── #
        zi = QAction("＋", self)
        zi.setToolTip(t("Zoom in  [ + ]"))
        zi.triggered.connect(self.zoom_in_requested)
        self.addAction(zi)

        zo = QAction("－", self)
        zo.setToolTip(t("Zoom out  [ - ]"))
        zo.triggered.connect(self.zoom_out_requested)
        self.addAction(zo)

    def set_tile_provider(self, key: str) -> None:
        idx = self._provider_combo.findData(key)
        if idx >= 0:
            self._provider_combo.blockSignals(True)
            self._provider_combo.setCurrentIndex(idx)
            self._provider_combo.blockSignals(False)

    def _emit_search(self) -> None:
        query = self._search_edit.text().strip()
        if query:
            self.search_requested.emit(query)


# ── MapToolbar (VS Code Activity Bar) ────────────────────────────────────────


class MapToolbar(QToolBar):
    """
    VS Code-style narrow vertical activity bar (left side).

    Sections:
      • Navigate  — Select / Pan / Lasso
      • Create    — polygon, rectangle, circle, pin, text
      • (bottom)  — Import, Print/PDF

    Signals
    -------
    tool_selected(str)  — ToolMode value emitted on tool activation
    import_requested()
    print_requested()
    """

    tool_selected = pyqtSignal(str)
    import_requested = pyqtSignal()
    print_requested = pyqtSignal()
    toggle_grid_requested = pyqtSignal(bool)
    # Emitted when the user types a degree value into the rotate spinbox
    rotate_degree_changed = pyqtSignal(float)

    # Navigate section: SELECT, PAN | ROTATE, MOVE | separator | MAGIC_WAND (Dynamic Selector)
    _NAVIGATE_TOOLS_PRIMARY: list[tuple[str, str, ToolMode]] = [
        ("⬡", "Select / move elements", ToolMode.SELECT),
        ("✋", "Pan the map", ToolMode.PAN),
    ]
    _ROTATE_MOVE_TOOLS: list[tuple[str, str, ToolMode]] = [
        ("↻", "Rotate zone (click zone, then ↑/↓ to rotate 1° at a time)", ToolMode.ROTATE_ELEMENT),
        ("✥", "Move element (click to pick, click to drop)", ToolMode.MOVE_ELEMENT),
    ]
    _LASSO_TOOL: tuple[str, str, ToolMode] = (
        "✦", "Dynamic Selector", ToolMode.MAGIC_WAND
    )
    _MEASURE_TOOL: tuple[str, str, ToolMode] = (
        "\U0001f4cf", "Measure distance on map (click points, Esc to clear)", ToolMode.MEASURE
    )
    _DIMENSION_TOOL: tuple[str, str, ToolMode] = (
        "↔", "Place a persistent dimension (click two points)", ToolMode.DIMENSION
    )
    _CREATE_TOOLS: list[tuple[str, str, ToolMode]] = [
        ("⬠", "Draw polygon zone", ToolMode.DRAW_POLYGON),
        ("▭", "Draw rectangle zone", ToolMode.DRAW_RECTANGLE),
        ("◯", "Draw circle zone", ToolMode.DRAW_CIRCLE),
        ("📍", "Place keypoint marker", ToolMode.DRAW_KEYPOINT),
        ("T", "Place text annotation", ToolMode.DRAW_TEXT),
    ]
    _TOOL_SHORTCUTS: dict[ToolMode, str] = {
        ToolMode.SELECT: "C",
        ToolMode.PAN: "H",
        ToolMode.ROTATE_ELEMENT: "R",
        ToolMode.MOVE_ELEMENT: "G",
        ToolMode.MAGIC_WAND: "L",
        ToolMode.MEASURE: "M",
        ToolMode.DIMENSION: "D",
        ToolMode.DRAW_POLYGON: "P",
        ToolMode.DRAW_RECTANGLE: "B",
        ToolMode.DRAW_CIRCLE: "O",
        ToolMode.DRAW_KEYPOINT: "K",
        ToolMode.DRAW_TEXT: "T",
    }

    # Tooltips are translated at widget-creation time via t().

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Activity", parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setStyleSheet(_TOOLBAR_QSS)

        self._tool_actions: dict[ToolMode, QAction] = {}
        self._group = QActionGroup(self)
        self._group.setExclusive(True)

        # ── Navigate: primary (Select / Pan) ──────────────────────────────── #
        for symbol, tooltip, mode in self._NAVIGATE_TOOLS_PRIMARY:
            act = QAction(symbol, self)
            act.setToolTip(self._tool_tooltip(tooltip, mode))
            act.setCheckable(True)
            act.setData(mode)
            act.triggered.connect(
                lambda checked, m=mode: (
                    self.tool_selected.emit(m),
                    self._rotate_container.setVisible(False),
                )
            )
            self._group.addAction(act)
            self.addAction(act)
            self._tool_actions[mode] = act

        # ── Navigate: Rotate + Move (no separator from primary) ───────────── #
        for symbol, tooltip, mode in self._ROTATE_MOVE_TOOLS:
            act = QAction(symbol, self)
            act.setToolTip(self._tool_tooltip(tooltip, mode))
            act.setCheckable(True)
            act.setData(mode)
            act.triggered.connect(
                lambda checked, m=mode: (
                    self.tool_selected.emit(m),
                    self._rotate_container.setVisible(m == ToolMode.ROTATE_ELEMENT),
                )
            )
            self._group.addAction(act)
            self.addAction(act)
            self._tool_actions[mode] = act

        # ── Rotate degree spinbox (hidden unless ROTATE_ELEMENT is active) ─── #
        self._rotate_container = QWidget(self)
        _rot_hbox_layout = QHBoxLayout(self._rotate_container)
        _rot_hbox_layout.setContentsMargins(2, 0, 2, 0)
        _rot_hbox_layout.setSpacing(2)
        self._rotate_spinbox = QDoubleSpinBox()
        self._rotate_spinbox.setRange(0.0, 359.9)
        self._rotate_spinbox.setDecimals(1)
        self._rotate_spinbox.setSuffix("°")
        self._rotate_spinbox.setWrapping(True)
        self._rotate_spinbox.setMinimumWidth(78)
        self._rotate_spinbox.setMaximumWidth(78)
        self._rotate_spinbox.setToolTip(t("Rotation angle — type a value or use ↑/↓ on the map"))
        self._rotate_spinbox.setStyleSheet(
            "QDoubleSpinBox { background:#3C3C3C; color:#D4D4D4;"
            " border:1px solid #555; border-radius:3px; padding:2px 4px; font-size:11px; }"
        )
        self._rotate_spinbox.valueChanged.connect(
            lambda v: self.rotate_degree_changed.emit(v)
        )
        _rot_hbox_layout.addWidget(self._rotate_spinbox)
        self._rotate_container.setVisible(False)
        self.addWidget(self._rotate_container)

        # ── Separator before Dynamic Selector (lasso) ─────────────────────── #
        self.addSeparator()

        # ── Lasso (Dynamic Selector) ──────────────────────────────────────── #
        symbol, tooltip, mode = self._LASSO_TOOL
        act = QAction(symbol, self)
        act.setToolTip(self._tool_tooltip(tooltip, mode))
        act.setCheckable(True)
        act.setData(mode)
        act.triggered.connect(
            lambda checked, m=mode: (
                self.tool_selected.emit(m),
                self._rotate_container.setVisible(False),
            )
        )
        self._group.addAction(act)
        self.addAction(act)
        self._tool_actions[mode] = act

        # ── Measure tool ──────────────────────────────────────────────────── #
        symbol, tooltip, mode = self._MEASURE_TOOL
        act = QAction(symbol, self)
        act.setToolTip(self._tool_tooltip(tooltip, mode))
        act.setCheckable(True)
        act.setData(mode)
        act.triggered.connect(
            lambda checked, m=mode: (
                self.tool_selected.emit(m),
                self._rotate_container.setVisible(False),
            )
        )
        self._group.addAction(act)
        self.addAction(act)
        self._tool_actions[mode] = act

        # ── Persistent dimension tool ───────────────────────────────────────
        symbol, tooltip, mode = self._DIMENSION_TOOL
        act = QAction(symbol, self)
        act.setToolTip(self._tool_tooltip(tooltip, mode))
        act.setCheckable(True)
        act.setData(mode)
        act.triggered.connect(
            lambda checked, m=mode: (
                self.tool_selected.emit(m),
                self._rotate_container.setVisible(False),
            )
        )
        self._group.addAction(act)
        self.addAction(act)
        self._tool_actions[mode] = act

        self.addSeparator()

        # ── Create ────────────────────────────────────────────────────────── #
        for symbol, tooltip, mode in self._CREATE_TOOLS:
            act = QAction(symbol, self)
            act.setToolTip(self._tool_tooltip(tooltip, mode))
            act.setCheckable(True)
            act.setData(mode)
            act.triggered.connect(
                lambda checked, m=mode: (
                    self.tool_selected.emit(m),
                    self._rotate_container.setVisible(False),
                )
            )
            self._group.addAction(act)
            self.addAction(act)
            self._tool_actions[mode] = act

        self.addSeparator()

        # ── Spacer — pushes right-side items to the right ────────────────── #
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.addWidget(spacer)

        # ── Grid precision-move toggle ────────────────────────────────────── #
        act_grid = QAction("▦", self)
        act_grid.setToolTip(t("Toggle coordinate grid (precision move)"))
        act_grid.setCheckable(True)
        act_grid.toggled.connect(self.toggle_grid_requested)
        self.addAction(act_grid)

        # ── Bottom utility actions ─────────────────────────────────────────── #
        act_import = QAction("⬇", self)
        act_import.setToolTip(t("Import GeoJSON…"))
        act_import.triggered.connect(self.import_requested)
        self.addAction(act_import)

        act_print = QAction("🖶", self)
        act_print.setToolTip(t("Print / Export PDF…"))
        act_print.triggered.connect(self.print_requested)
        self.addAction(act_print)

        self.addWidget(create_help_button(self, self._show_help))

        # Default tool
        self._tool_actions[ToolMode.PAN].setChecked(True)

    def _show_help(self) -> None:
        show_help_dialog(self, t("Application Help"), t("Map tools help"))

    @classmethod
    def _tool_tooltip(cls, text: str, mode: ToolMode) -> str:
        shortcut = cls._TOOL_SHORTCUTS.get(mode)
        return f"{t(text)} [{shortcut}]" if shortcut else t(text)

    def set_tool(self, mode: ToolMode) -> None:
        action = self._tool_actions.get(mode)
        if action:
            action.setChecked(True)
        self._rotate_container.setVisible(mode == ToolMode.ROTATE_ELEMENT)

    def set_rotate_angle(self, degrees: float) -> None:
        """Update the rotate spinbox without re-emitting rotate_degree_changed."""
        self._rotate_spinbox.blockSignals(True)
        self._rotate_spinbox.setValue(degrees % 360.0)
        self._rotate_spinbox.blockSignals(False)
