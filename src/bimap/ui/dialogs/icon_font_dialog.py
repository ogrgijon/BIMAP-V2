"""Searchable icon-font picker for keypoint markers."""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from bimap.data.icon_font import ICON_CATALOG, icon_font_family, icon_glyph, icon_value
from bimap.i18n import t


class IconFontDialog(QDialog):
    """Display every icon in the available icon catalog with live filtering."""

    def __init__(self, current: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Choose Font Icon"))
        self.setMinimumSize(620, 480)
        self.selected_value = current
        self._buttons: list[tuple[QPushButton, str, str]] = []

        layout = QVBoxLayout(self)
        self._search = QLineEdit()
        self._search.setPlaceholderText(t("Search icons..."))
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self._grid = QGridLayout(content)
        self._grid.setSpacing(6)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        family = icon_font_family() or "Segoe UI Symbol"
        for index, entry in enumerate(ICON_CATALOG):
            name, label, _, _ = entry
            button = QPushButton(f"{icon_glyph(entry)}\n{label}")
            button.setCheckable(True)
            button.setMinimumSize(112, 76)
            button.setFont(QFont(family, 16))
            button.setToolTip(name)
            value = icon_value(name)
            button.clicked.connect(lambda _, val=value: self._select(val))
            self._grid.addWidget(button, index // 5, index % 5)
            self._buttons.append((button, value, f"{name} {label}".lower()))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._select(current)

    def _select(self, value: str) -> None:
        if any(item_value == value for _, item_value, _ in self._buttons):
            self.selected_value = value
        for button, item_value, _ in self._buttons:
            button.setChecked(item_value == self.selected_value)

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for button, _, searchable in self._buttons:
            button.setVisible(not needle or needle in searchable)