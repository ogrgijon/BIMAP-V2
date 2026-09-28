"""Beautiful read-only metadata viewer dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import add_top_right_help_button, show_help_dialog


class MetadataViewDialog(QDialog):
    """Read-only dialog displaying an element's key-value metadata in a polished layout."""

    def __init__(
        self,
        element_name: str,
        element_type: str,
        metadata: dict[str, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Metadata — {element_name}")
        self.setMinimumSize(420, 300)
        self.resize(500, 380)
        self._setup_ui(element_name, element_type, metadata)

    def _setup_ui(
        self, name: str, etype: str, metadata: dict[str, str]
    ) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)
        add_top_right_help_button(self, self._show_help)

        # ── Header ─────────────────────────────────────────────────────────── #
        icon = {"zone": "⬡", "keypoint": "📍", "annotation": "T"}.get(etype, "●")
        header = QLabel(f"  {icon}  {etype.title()}: {name}")
        header.setStyleSheet(
            "font-size: 14px; font-weight: bold;"
            "padding: 8px 12px;"
            "background: #252526;"
            "border-left: 4px solid #007ACC;"
            "border-radius: 2px;"
        )
        root.addWidget(header)

        # ── Content ────────────────────────────────────────────────────────── #
        if not metadata:
            empty = QLabel(t("No metadata entries for this element."))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #858585; font-style: italic; padding: 20px;")
            root.addWidget(empty)
        else:
            count_label = QLabel(f"{len(metadata)} entr{'y' if len(metadata) == 1 else 'ies'}")
            count_label.setStyleSheet("font-size: 11px; color: #858585;")
            root.addWidget(count_label)

            table = QTableWidget(len(metadata), 2)
            table.setHorizontalHeaderLabels([t("Key"), t("Value")])
            table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.Stretch
            )
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setShowGrid(False)
            table.setStyleSheet(
                "QTableWidget { border: 1px solid #3C3C3C; border-radius: 4px; }"
                "QTableWidget::item { padding: 6px 10px; }"
                "QHeaderView::section {"
                "  background: #2D2D2D; color: #9CDCFE;"
                "  padding: 4px 10px; border-bottom: 1px solid #3C3C3C; font-weight: bold;"
                "}"
            )

            for i, (k, v) in enumerate(metadata.items()):
                key_item = QTableWidgetItem(k)
                key_item.setForeground(Qt.GlobalColor.white)
                val_item = QTableWidgetItem(v)
                table.setItem(i, 0, key_item)
                table.setItem(i, 1, val_item)

            root.addWidget(table)

        # ── Close button ───────────────────────────────────────────────────── #
        btn_close = QPushButton(t("Close"))
        btn_close.setDefault(True)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    def _show_help(self) -> None:
        show_help_dialog(self, t("Application Help"), t("Metadata Viewer window help"))
