"""OGC autodiscover dialog — fetches GetCapabilities and lets the user pick a layer."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import requests
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button

_HTTP_HEADERS = {"User-Agent": "BIMAP/1.0"}


class _DiscoverWorker(QThread):
    """Background thread that fetches GetCapabilities and parses layers."""

    finished: pyqtSignal = pyqtSignal(list)
    error: pyqtSignal = pyqtSignal(str)

    def __init__(self, service_type: str, url: str) -> None:
        super().__init__()
        self._service_type = service_type
        self._url = url

    def run(self) -> None:  # noqa: D102
        try:
            params = {"SERVICE": self._service_type, "REQUEST": "GetCapabilities"}
            resp = requests.get(
                self._url, params=params, headers=_HTTP_HEADERS, timeout=15
            )
            resp.raise_for_status()
            items = self._parse_wfs(resp.text)
            self.finished.emit(items)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))

    def _parse_wfs(self, xml_text: str) -> list[dict[str, Any]]:
        from bimap.data.wfs_source import _parse_capabilities_full  # type: ignore[attr-defined]

        entries = _parse_capabilities_full(xml_text)
        return [
            {
                "name": e["name"],
                "title": e.get("title", ""),
                "min_lon": e.get("min_lon"),
                "min_lat": e.get("min_lat"),
                "max_lon": e.get("max_lon"),
                "max_lat": e.get("max_lat"),
            }
            for e in entries
        ]


class OgcDiscoverDialog(QDialog):
    """Fetch WFS GetCapabilities and let the user pick a feature type.

    Usage::

        dlg = OgcDiscoverDialog("WFS", url="https://…/wfs", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            type_name = dlg.selected_name
            title      = dlg.selected_title
            extent     = dlg.selected_extent  # [min_lat, min_lon, max_lat, max_lon]
    """

    def __init__(
        self,
        service_type: str,
        url: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service_type = service_type.upper()  # "WFS"
        self._items: list[dict[str, Any]] = []
        self._worker: _DiscoverWorker | None = None
        self._selected: dict[str, Any] | None = None

        self.setWindowTitle(
            t("Discover {svc} Layers").format(svc=self._service_type)
        )
        self.setMinimumSize(650, 440)
        self._setup_ui(url)

        # Auto-connect when URL is pre-filled
        if url.strip():
            self._on_connect()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self, initial_url: str) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # URL row
        url_grp = QGroupBox(t("Service URL"))
        url_row = QHBoxLayout(url_grp)
        self._url_edit = QLineEdit(initial_url)
        self._url_edit.setPlaceholderText("https://…")
        self._url_edit.setToolTip(t("URL of a WFS service exposing GetCapabilities"))
        self._url_edit.returnPressed.connect(self._on_connect)
        self._connect_btn = QPushButton(t("Connect & Discover"))
        self._connect_btn.setToolTip(t("Retrieve the available feature types from this service"))
        self._connect_btn.setDefault(True)
        self._connect_btn.clicked.connect(self._on_connect)
        url_row.addWidget(self._url_edit, 1)
        url_row.addWidget(self._connect_btn)
        root.addWidget(url_grp)

        # Status label
        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._status_lbl)

        # Results table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(
            [t("Feature Type"), t("Title"), t("Bounding Box")]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(lambda _: self._try_accept())
        root.addWidget(self._table, 1)

        # OK / Cancel
        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setEnabled(False)
        self._btn_box.accepted.connect(self._try_accept)
        self._btn_box.rejected.connect(self.reject)
        add_dialog_help_button(self._btn_box, self, "Discover WFS window help")
        root.addWidget(self._btn_box)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_connect(self) -> None:
        url = self._url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, t("No URL"), t("Enter a service URL first."))
            return
        self._table.setRowCount(0)
        self._items = []
        self._connect_btn.setEnabled(False)
        ok_btn = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setEnabled(False)
        self._status_lbl.setText(t("Fetching GetCapabilities…"))

        self._worker = _DiscoverWorker(self._service_type, url)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, items: list[dict[str, Any]]) -> None:
        self._connect_btn.setEnabled(True)
        self._items = items
        if not items:
            self._status_lbl.setText(t("No layers found."))
            return

        n = len(items)
        self._status_lbl.setText(t("{n} layer(s) found — double-click or select and press OK.").format(n=n))
        self._table.setRowCount(n)
        for row, item in enumerate(items):
            self._table.setItem(row, 0, QTableWidgetItem(item.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(item.get("title", "")))
            min_lon = item.get("min_lon")
            min_lat = item.get("min_lat")
            if min_lon is not None and min_lat is not None:
                bbox_str = (
                    f"{min_lon:.3f},{min_lat:.3f} → "
                    f"{item['max_lon']:.3f},{item['max_lat']:.3f}"
                )
            else:
                bbox_str = ""
            self._table.setItem(row, 2, QTableWidgetItem(bbox_str))

        self._table.selectRow(0)

    def _on_error(self, msg: str) -> None:
        self._connect_btn.setEnabled(True)
        self._status_lbl.setText(f"Error: {msg}")
        QMessageBox.critical(self, t("Connection Error"), msg)

    def _on_selection_changed(self) -> None:
        has_selection = bool(self._table.selectedItems())
        ok_btn = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setEnabled(has_selection)

    def _try_accept(self) -> None:
        row = self._table.currentRow()
        if 0 <= row < len(self._items):
            self._selected = self._items[row]
            self.accept()

    # ── Result properties ─────────────────────────────────────────────────────

    @property
    def selected_name(self) -> str:
        """The layer name or feature type name chosen by the user."""
        return self._selected.get("name", "") if self._selected else ""

    @property
    def selected_title(self) -> str:
        """Human-readable title for the selected layer."""
        return self._selected.get("title", "") if self._selected else ""

    @property
    def selected_bbox(self) -> str:
        """Bounding box as ``"minx,miny,maxx,maxy"`` string or empty string."""
        if not self._selected:
            return ""
        try:
            min_lon = float(self._selected["min_lon"])  # type: ignore[arg-type]
            min_lat = float(self._selected["min_lat"])  # type: ignore[arg-type]
            max_lon = float(self._selected["max_lon"])  # type: ignore[arg-type]
            max_lat = float(self._selected["max_lat"])  # type: ignore[arg-type]
            return f"{min_lon},{min_lat},{max_lon},{max_lat}"
        except (KeyError, TypeError, ValueError):
            return ""

    @property
    def selected_extent(self) -> list[float]:
        """Geographic extent as ``[min_lat, min_lon, max_lat, max_lon]`` or ``[]``."""
        if not self._selected:
            return []
        try:
            return [
                float(self._selected["min_lat"]),  # type: ignore[arg-type]
                float(self._selected["min_lon"]),  # type: ignore[arg-type]
                float(self._selected["max_lat"]),  # type: ignore[arg-type]
                float(self._selected["max_lon"]),  # type: ignore[arg-type]
            ]
        except (KeyError, TypeError, ValueError):
            return []
