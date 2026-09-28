"""Geocode (address search) dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bimap.engine.geocoding import GeoResult, geocode
from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button


class GeocodeDialog(QDialog):
    """Simple address search using Nominatim."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Search Location"))
        self.setMinimumWidth(420)
        self._result: GeoResult | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("Enter address or place name:")))

        search_row_widget = QWidget()
        from PyQt6.QtWidgets import QHBoxLayout
        row = QHBoxLayout(search_row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        self._input = QLineEdit()
        self._input.setPlaceholderText(t("e.g. Madrid, Spain"))
        self._input.returnPressed.connect(self._do_search)
        btn = QPushButton(t("Search"))
        btn.clicked.connect(self._do_search)
        row.addWidget(self._input)
        row.addWidget(btn)
        layout.addWidget(search_row_widget)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        self._status = QLabel("")
        layout.addWidget(self._status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        add_dialog_help_button(buttons, self, "Search Location window help")
        layout.addWidget(buttons)

    def _do_search(self) -> None:
        query = self._input.text().strip()
        if not query:
            return
        self._status.setText(t("Searching…"))
        self._list.clear()
        results = geocode(query)
        if not results:
            self._status.setText(t("No results found."))
            return
        self._results = results
        for r in results:
            it = QListWidgetItem(r.display_name)
            self._list.addItem(it)
        self._status.setText(f"{len(results)} result(s) found.")

    def _on_double_click(self, item: QListWidgetItem) -> None:
        self._on_accept()

    def _on_accept(self) -> None:
        selected = self._list.selectedItems()
        if not selected:
            return
        idx = self._list.row(selected[0])
        self._result = self._results[idx]
        self.accept()

    @property
    def result(self) -> GeoResult | None:
        return self._result
