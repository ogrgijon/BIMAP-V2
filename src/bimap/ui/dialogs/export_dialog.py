"""PDF export settings dialog."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bimap.config import PDF_PAGE_SIZES
from bimap.i18n import t
from bimap.models.pdf_layout import PageOrientation, PDFLayout
from bimap.ui._utils import add_dialog_help_button


class ExportDialog(QDialog):
    """Configure PDF export settings and choose output path."""

    def __init__(self, layout: PDFLayout, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Export PDF"))
        self.setMinimumWidth(380)
        self._layout = layout
        self._output_path: str = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        grp = QGroupBox(t("Page Settings"))
        form = QFormLayout(grp)

        self._size_combo = QComboBox()
        for key in PDF_PAGE_SIZES:
            self._size_combo.addItem(key)
        self._size_combo.setCurrentText(self._layout.page_size)
        form.addRow(t("Page Size"), self._size_combo)

        self._orient_combo = QComboBox()
        self._orient_combo.addItems(["landscape", "portrait"])
        self._orient_combo.setCurrentText(self._layout.orientation)
        form.addRow(t("Orientation"), self._orient_combo)

        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 600)
        self._dpi_spin.setSingleStep(50)
        self._dpi_spin.setValue(self._layout.dpi)
        form.addRow(t("DPI"), self._dpi_spin)

        root.addWidget(grp)

        # Output path row
        path_widget = QWidget()
        path_row = QHBoxLayout(path_widget)
        path_row.setContentsMargins(0, 0, 0, 0)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(t("Output file path…"))
        btn_browse = QPushButton(t("Browse…"))
        btn_browse.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(btn_browse)
        root.addWidget(QLabel(t("Output File:")))
        root.addWidget(path_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        add_dialog_help_button(buttons, self, "Export PDF window help")
        root.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, t("Save PDF"), "", t("PDF Files (*.pdf)")
        )
        if path:
            self._path_edit.setText(path)

    def _on_accept(self) -> None:
        path = self._path_edit.text().strip()
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self._output_path = path
        self._layout.page_size = self._size_combo.currentText()
        self._layout.orientation = PageOrientation(self._orient_combo.currentText())
        self._layout.dpi = self._dpi_spin.value()
        self.accept()

    @property
    def output_path(self) -> str:
        return self._output_path
