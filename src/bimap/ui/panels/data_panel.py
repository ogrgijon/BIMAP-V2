"""Data sources manager panel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.models.data_source import DataSource
from bimap.ui._utils import create_help_button, show_help_dialog

# ── Colour palette for states ─────────────────────────────────────────────────
_DOT_OK = "color: #22c55e; font-size: 11px;"          # green
_DOT_ERROR = "color: #ef4444; font-size: 11px;"       # red
_DOT_CONNECTING = "color: #f97316; font-size: 11px;"  # orange
_DOT_IDLE = "color: #9ca3af; font-size: 11px;"        # grey

_TYPE_COLORS: dict[str, str] = {
    "wfs":        "#3b82f6",  # blue
    "geojson":    "#10b981",  # teal
    "csv":        "#f59e0b",  # amber
    "excel":      "#f59e0b",
    "rest_api":   "#ec4899",  # pink
    "sql":        "#6366f1",  # indigo
    "gsheets":    "#22c55e",  # green
}


def _fmt_time(iso: str) -> str:
    """Return a short human-readable time string from an ISO 8601 datetime."""
    try:
        dt = datetime.fromisoformat(iso)
        now = datetime.now()
        delta = now - dt
        if delta.total_seconds() < 60:
            return t("just now")
        if delta.total_seconds() < 3600:
            return t("{m}m ago").format(m=int(delta.total_seconds() // 60))
        if delta.days == 0:
            return dt.strftime("%H:%M:%S")
        return dt.strftime("%d/%m %H:%M")
    except (ValueError, OSError):
        return iso[:19] if iso else ""


# ── Source card widget ────────────────────────────────────────────────────────

class _SourceCard(QFrame):
    """Compact info card for one DataSource row."""

    _NORMAL_BG = ""                          # default (stylesheet-driven)
    _SELECTED_BG = "background: #dbeafe; border: 1px solid #93c5fd; border-radius: 4px;"

    def set_selected(self, selected: bool) -> None:
        self.setStyleSheet(self._SELECTED_BG if selected else self._NORMAL_BG)

    def __init__(self, ds: DataSource, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(1)

        # ── Row 1: dot · name · type badge ───────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(4)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(14)
        top.addWidget(self._dot)

        self._name_lbl = QLabel()
        self._name_lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
        top.addWidget(self._name_lbl, 1)

        self._type_lbl = QLabel()
        self._type_lbl.setStyleSheet("font-size: 9px; padding: 1px 4px; border-radius: 3px;")
        top.addWidget(self._type_lbl)

        root.addLayout(top)

        # ── Row 2: status line ────────────────────────────────────────────────
        self._status_lbl = QLabel()
        self._status_lbl.setStyleSheet("color: #6b7280; font-size: 10px; padding-left: 18px;")
        root.addWidget(self._status_lbl)

        # ── Row 3: error line (hidden when no error) ─────────────────────────
        self._error_lbl = QLabel()
        self._error_lbl.setStyleSheet("color: #ef4444; font-size: 10px; padding-left: 18px;")
        self._error_lbl.setWordWrap(True)
        self._error_lbl.setVisible(False)
        root.addWidget(self._error_lbl)

        self.update_ds(ds)

    def update_ds(self, ds: DataSource) -> None:
        """Re-render the card with fresh data from *ds*."""
        self._name_lbl.setText(ds.name)

        # Type badge
        color = _TYPE_COLORS.get(str(ds.source_type), "#6b7280")
        self._type_lbl.setText(str(ds.source_type).upper())
        self._type_lbl.setStyleSheet(
            f"font-size: 9px; padding: 1px 4px; border-radius: 3px;"
            f" background: {color}22; color: {color}; border: 1px solid {color}55;"
        )

        # Status dot + line
        state = getattr(ds, "connection_state", "")
        if state == "connecting":
            self._dot.setStyleSheet(_DOT_CONNECTING)
            self._dot.setToolTip(t("Connecting…"))
            status = t("Connecting…")
        elif ds.last_error or state == "error":
            self._dot.setStyleSheet(_DOT_ERROR)
            self._dot.setToolTip(t("Error"))
            status = t("Error")
        elif ds.last_refresh:
            self._dot.setStyleSheet(_DOT_OK)
            self._dot.setToolTip(t("Connected"))
            row_part = (
                t("{n} rows").format(n=getattr(ds, "row_count", 0))
                if getattr(ds, "row_count", 0) else ""
            )
            ms = getattr(ds, "last_refresh_ms", 0)
            ms_part = f"{ms}\u202fms" if ms else ""
            time_part = _fmt_time(ds.last_refresh)
            parts = [p for p in (time_part, row_part, ms_part) if p]
            status = "  ·  ".join(parts)
        else:
            self._dot.setStyleSheet(_DOT_IDLE)
            self._dot.setToolTip(t("Not refreshed"))
            mode = str(getattr(ds, "refresh_mode", "manual"))
            status = t("Never refreshed  [{mode}]").format(mode=mode)

        self._status_lbl.setText(status)

        if ds.last_error:
            truncated = ds.last_error if len(ds.last_error) <= 120 else ds.last_error[:117] + "…"
            self._error_lbl.setText(truncated)
            self._error_lbl.setVisible(True)
        else:
            self._error_lbl.setVisible(False)


# ── Panel ─────────────────────────────────────────────────────────────────────

class DataPanel(QWidget):
    """
    Lists configured data sources and lets the user add/edit/remove/refresh them.

    Signals
    -------
    add_requested()
    edit_requested(source_id_str)
    remove_requested(source_id_str)
    refresh_requested(source_id_str)
    """

    add_requested = pyqtSignal()
    edit_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal(str)
    fit_requested = pyqtSignal(str)      # fly-to data extent

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project = None
        self._cards: dict[str, _SourceCard] = {}   # source_id → card widget
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(4)

        title_row = QHBoxLayout()
        title = QLabel(t("Data Sources"))
        title.setStyleSheet("font-weight: bold; padding: 2px;")
        title_row.addWidget(title, 1)
        title_row.addWidget(create_help_button(self, self._show_help))
        layout.addLayout(title_row)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setSpacing(2)
        self._list.setStyleSheet(
            "QListWidget { outline: 0; }"
            "QListWidget::item { border-radius: 4px; padding: 2px; }"
            "QListWidget::item:selected { background: transparent; }"
        )
        self._list.currentItemChanged.connect(self._on_selection_highlight)
        layout.addWidget(self._list)

        # Buttons
        btn_row1 = QHBoxLayout()
        btn_add = QPushButton(t("+ Add"))
        btn_add.setToolTip(t("Add and configure a new data source"))
        btn_add.clicked.connect(self.add_requested)
        btn_edit = QPushButton(t("Edit"))
        btn_edit.setToolTip(t("Edit the selected data source configuration"))
        btn_edit.clicked.connect(self._on_edit)
        btn_row1.addWidget(btn_add)
        btn_row1.addWidget(btn_edit)
        layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        self._btn_refresh = QPushButton(t("⟳ Refresh"))
        self._btn_refresh.setToolTip(t("Reload data from the selected source"))
        self._btn_refresh.clicked.connect(self._on_refresh)
        btn_remove = QPushButton(t("Remove"))
        btn_remove.setToolTip(t("Remove the selected data source from the project"))
        btn_remove.clicked.connect(self._on_remove)
        btn_fly = QPushButton(t("🎯 Fly to"))
        btn_fly.setToolTip(t("Zoom map to the extent of this data source"))
        btn_fly.clicked.connect(self._on_fly)
        btn_row2.addWidget(self._btn_refresh)
        btn_row2.addWidget(btn_fly)
        btn_row2.addWidget(btn_remove)
        layout.addLayout(btn_row2)

    def _show_help(self) -> None:
        show_help_dialog(self, t("Panel Help"), t("Data Sources panel help"))

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self, project: Any) -> None:
        """Rebuild the list from *project*."""
        self._project = project
        self._list.clear()
        self._cards.clear()
        for ds in project.data_sources:
            self._add_item(ds)

    def set_connecting(self, source_id: str) -> None:
        """Mark a source as 'connecting' while a refresh is in progress."""
        ds = self._find_ds(source_id)
        if ds:
            ds.connection_state = "connecting"
            ds.last_error = ""
            self._refresh_card(source_id, ds)
        self._btn_refresh.setEnabled(False)
        self._btn_refresh.setText(t("⟳ Connecting…"))

    def update_source_status(self, source_id: str, error: str = "") -> None:
        """Called after a refresh succeeds or fails."""
        ds = self._find_ds(source_id)
        if ds:
            ds.last_error = error
            ds.connection_state = "error" if error else "ok"
            self._refresh_card(source_id, ds)
        self._btn_refresh.setEnabled(True)
        self._btn_refresh.setText(t("⟳ Refresh"))

    def set_refreshed(self, source_id: str, row_count: int, ms: int) -> None:
        """Store performance statistics after a successful fetch."""
        ds = self._find_ds(source_id)
        if ds:
            ds.row_count = row_count
            ds.last_refresh_ms = ms
            self._refresh_card(source_id, ds)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _add_item(self, ds: DataSource) -> None:
        card = _SourceCard(ds)
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, str(ds.id))
        item.setSizeHint(card.sizeHint())
        self._list.addItem(item)
        self._list.setItemWidget(item, card)
        self._cards[str(ds.id)] = card

    def _refresh_card(self, source_id: str, ds: DataSource) -> None:
        card = self._cards.get(source_id)
        if card:
            card.update_ds(ds)
            # Resize the item to match potentially changed card height
            for i in range(self._list.count()):
                it = self._list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == source_id:
                    it.setSizeHint(card.sizeHint())
                    break

    def _find_ds(self, source_id: str) -> DataSource | None:
        if self._project:
            for ds in self._project.data_sources:
                if str(ds.id) == source_id:
                    return ds
        return None

    def _selected_id(self) -> str | None:
        selected = self._list.selectedItems()
        if selected:
            return selected[0].data(Qt.ItemDataRole.UserRole)
        return None

    def _on_edit(self) -> None:
        sid = self._selected_id()
        if sid:
            self.edit_requested.emit(sid)

    def _on_remove(self) -> None:
        sid = self._selected_id()
        if sid:
            self.remove_requested.emit(sid)

    def _on_refresh(self) -> None:
        sid = self._selected_id()
        if sid:
            self.refresh_requested.emit(sid)

    def _on_fly(self) -> None:
        sid = self._selected_id()
        if sid:
            self.fit_requested.emit(sid)

    def _on_selection_highlight(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        """Update card background colours to reflect the current selection."""
        if previous:
            prev_id = previous.data(Qt.ItemDataRole.UserRole)
            card = self._cards.get(prev_id)
            if card:
                card.set_selected(False)
        if current:
            curr_id = current.data(Qt.ItemDataRole.UserRole)
            card = self._cards.get(curr_id)
            if card:
                card.set_selected(True)
