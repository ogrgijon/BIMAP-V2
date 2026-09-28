"""Delimitation dialog — search for an administrative boundary and apply it to the map."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bimap.engine.delimitation import DelimitationResult, fetch_places_with_polygon
from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button


class DelimitationDialog(QDialog):
    """
    Search for a city, province, country, or other administrative boundary via
    Nominatim and set it as the active map delimitation.

    The dialog returns::

        dlg.result_item   -> DelimitationResult | None
        dlg.clear_mode    -> bool  (True when the user clicked "Clear")
    """

    def __init__(self, current_name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Set Delimitation"))
        self.setMinimumWidth(480)
        self.result_item: DelimitationResult | None = None
        self.clear_mode: bool = False
        self._results: list[DelimitationResult] = []
        self._setup_ui(current_name)

    def _setup_ui(self, current_name: str) -> None:
        layout = QVBoxLayout(self)

        if current_name:
            layout.addWidget(
                QLabel(f"<b>{t('Current delimitation:')}</b> {current_name}")
            )

        layout.addWidget(QLabel(t("Search for a city, province, country, etc.:")))

        row_w = QWidget()
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        self._input = QLineEdit()
        self._input.setPlaceholderText("e.g.  Madrid  |  Catalonia  |  Argentina")
        self._input.returnPressed.connect(self._do_search)
        btn_search = QPushButton(t("Search"))
        btn_search.clicked.connect(self._do_search)
        row.addWidget(self._input)
        row.addWidget(btn_search)
        layout.addWidget(row_w)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        btn_box = QDialogButtonBox()
        btn_ok = btn_box.addButton(QDialogButtonBox.StandardButton.Ok)
        btn_clear = btn_box.addButton(t("Clear Delimitation"), QDialogButtonBox.ButtonRole.ResetRole)
        btn_cancel = btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        btn_ok.clicked.connect(self._on_accept)
        btn_clear.clicked.connect(self._on_clear)
        btn_cancel.clicked.connect(self.reject)
        add_dialog_help_button(btn_box, self, "Set Delimitation window help")
        layout.addWidget(btn_box)

    def _do_search(self) -> None:
        query = self._input.text().strip()
        if not query:
            return
        self._status.setText(t("Searching…"))
        self._list.clear()
        results = fetch_places_with_polygon(query)
        if not results:
            self._status.setText(t("No results found."))
            return
        self._results = results
        for r in results:
            has_poly = "✓ polygon" if r.polygon else "bbox only"
            item = QListWidgetItem(f"{r.name}  [{has_poly}]")
            self._list.addItem(item)
        self._status.setText(f"{len(results)} result(s). Double-click or select + OK.")

    def _on_double_click(self, item: QListWidgetItem) -> None:
        self._on_accept()

    def _on_accept(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._results):
            self._status.setText(t("Please select a result first."))
            return
        self.result_item = self._results[row]
        self.accept()

    def _on_clear(self) -> None:
        self.clear_mode = True
        self.accept()
