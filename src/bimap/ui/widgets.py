"""Shared reusable Qt widgets for the BIMAP UI."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QPushButton, QWidget

from bimap.i18n import t


class ColorButton(QPushButton):
    """A color-swatch button that shows the hex value and opens a full color picker."""

    color_changed = pyqtSignal(str)

    def __init__(self, color: str = "#3388FF", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedHeight(28)
        self.setMinimumWidth(90)
        self._update_style()
        self.clicked.connect(self._pick_color)

    def set_color(self, color: str) -> None:
        self._color = color
        self._update_style()

    def color(self) -> str:
        return self._color

    def _update_style(self) -> None:
        c = QColor(self._color)
        luminance = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        label_color = "#111111" if luminance > 140 else "#FFFFFF"
        self.setText(self._color.upper())
        self.setStyleSheet(
            f"background-color: {self._color};"
            f"color: {label_color};"
            "border: 1px solid #666;"
            "border-radius: 4px;"
            "font-size: 10px;"
            "font-family: monospace;"
            "padding: 0 4px;"
        )

    def _pick_color(self) -> None:
        from PyQt6.QtWidgets import QColorDialog as _QCD
        dlg = _QCD(QColor(self._color), self)
        dlg.setWindowTitle(t("Choose Color"))
        dlg.setOption(_QCD.ColorDialogOption.ShowAlphaChannel)
        dlg.setOption(_QCD.ColorDialogOption.DontUseNativeDialog)
        dlg.setStyleSheet(
            "QColorDialog, QWidget { background-color: #2d2d2d; color: #d4d4d4; }"
            "QPushButton { background-color: #3c3c3c; color: #d4d4d4; "
            "border: 1px solid #555; border-radius: 3px; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #505050; }"
        )
        if dlg.exec():
            col = dlg.selectedColor()
            if col.isValid():
                self._color = col.name()
                self._update_style()
                self.color_changed.emit(self._color)
