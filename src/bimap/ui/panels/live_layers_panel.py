"""LiveLayersPanel — dock widget listing all live-feed layers with status."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.models.live_layer import LiveLayer
from bimap.ui._utils import create_help_button, show_help_dialog


# Status colours
_STATUS_COLORS = {
    "live":    QColor("#22c55e"),   # green
    "polling": QColor("#f97316"),   # orange
    "error":   QColor("#ef4444"),   # red
    "paused":  QColor("#9ca3af"),   # grey
}

_DOT = "●"


def _dot_for() -> str:
    return _DOT


class LiveLayersPanel(QWidget):
    """Sidebar panel that lists active live-feed layers.

    Signals
    -------
    layer_add_requested
        User clicked Add.
    layer_edit_requested(layer_id)
        User double-clicked a row or clicked Edit.
    layer_toggle_requested(layer_id)
        User toggled pause/resume on a row.
    layer_remove_requested(layer_id)
        User confirmed removal of a row.
    layer_visibility_changed(layer_id, visible)
        User toggled the visible flag.
    """

    layer_add_requested = pyqtSignal()
    layer_edit_requested = pyqtSignal(str)
    layer_toggle_requested = pyqtSignal(str)
    layer_remove_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layers: list[LiveLayer] = []
        self._statuses: dict[str, str] = {}   # layer_id → status key
        self._counts: dict[str, int] = {}     # layer_id → marker count
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize().__class__(16, 16))

        self._add_btn = QPushButton(t("add_live_feed"))
        self._add_btn.setToolTip(t("Add a live data feed"))
        self._add_btn.setFlat(True)
        self._add_btn.clicked.connect(self.layer_add_requested)

        self._edit_btn = QPushButton(t("edit"))
        self._edit_btn.setToolTip(t("Edit the selected live feed configuration"))
        self._edit_btn.setFlat(True)
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit)

        self._toggle_btn = QPushButton(t("pause"))
        self._toggle_btn.setToolTip(t("Pause or resume polling for the selected live feed"))
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setEnabled(False)
        self._toggle_btn.clicked.connect(self._on_toggle)

        self._remove_btn = QPushButton(t("remove"))
        self._remove_btn.setToolTip(t("Remove the selected live feed"))
        self._remove_btn.setFlat(True)
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(4, 2, 4, 2)
        btn_row.setSpacing(4)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._edit_btn)
        btn_row.addWidget(self._toggle_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._remove_btn)
        btn_row.addWidget(create_help_button(self, self._show_help))
        root.addLayout(btn_row)

        # List
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.currentRowChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(lambda _: self._on_edit())
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self._list)

    def _show_help(self) -> None:
        show_help_dialog(self, t("Panel Help"), t("Live Feeds panel help"))

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_layers(self, layers: list[LiveLayer]) -> None:
        """Replace the displayed layer list."""
        self._layers = list(layers)
        self._rebuild_list()

    def set_status(self, layer_id: str, status: str) -> None:
        """Update the status dot for a layer.  status in {live,polling,error,paused}."""
        self._statuses[layer_id] = status
        self._update_row(layer_id)

    def set_count(self, layer_id: str, count: int) -> None:
        """Update the marker-count badge for a layer."""
        self._counts[layer_id] = count
        self._update_row(layer_id)

    def clear_layer(self, layer_id: str) -> None:
        """Remove a layer entry (called after deletion)."""
        self._statuses.pop(layer_id, None)
        self._counts.pop(layer_id, None)
        self._layers = [l for l in self._layers if l.id != layer_id]
        self._rebuild_list()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _rebuild_list(self) -> None:
        self._list.clear()
        for layer in self._layers:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, layer.id)
            self._list.addItem(item)
            self._update_row_item(item, layer)

    def _update_row(self, layer_id: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == layer_id:
                layer = next((l for l in self._layers if l.id == layer_id), None)
                if layer:
                    self._update_row_item(item, layer)
                break

    def _update_row_item(self, item: QListWidgetItem, layer: LiveLayer) -> None:
        status = self._statuses.get(layer.id, "paused")
        count = self._counts.get(layer.id, 0)
        color = _STATUS_COLORS.get(status, _STATUS_COLORS["paused"])
        dot_text = _dot_for()
        count_str = f" ({count})" if count else ""
        item.setText(f"{dot_text} {layer.name}{count_str}")
        item.setForeground(color)

    def _current_layer_id(self) -> str | None:
        item = self._list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_selection_changed(self, row: int) -> None:
        has = row >= 0
        self._edit_btn.setEnabled(has)
        self._toggle_btn.setEnabled(has)
        self._remove_btn.setEnabled(has)
        if has:
            lid = self._current_layer_id()
            status = self._statuses.get(lid or "", "paused")
            self._toggle_btn.setText(
                t("resume") if status == "paused" else t("pause")
            )

    def _on_edit(self) -> None:
        lid = self._current_layer_id()
        if lid:
            self.layer_edit_requested.emit(lid)

    def _on_toggle(self) -> None:
        lid = self._current_layer_id()
        if lid:
            self.layer_toggle_requested.emit(lid)

    def _on_remove(self) -> None:
        lid = self._current_layer_id()
        if lid:
            self.layer_remove_requested.emit(lid)

    def _show_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if not item:
            return
        lid = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction(t("edit"), lambda: self.layer_edit_requested.emit(lid))
        status = self._statuses.get(lid, "paused")
        if status == "paused":
            menu.addAction(t("resume"), lambda: self.layer_toggle_requested.emit(lid))
        else:
            menu.addAction(t("pause"), lambda: self.layer_toggle_requested.emit(lid))
        menu.addSeparator()
        menu.addAction(t("remove"), lambda: self.layer_remove_requested.emit(lid))
        menu.exec(self._list.viewport().mapToGlobal(pos))
