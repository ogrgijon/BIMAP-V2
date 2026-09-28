"""Keynotes panel — numbered keynote list editor."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import create_help_button, show_help_dialog


class KeynotesPanel(QWidget):
    """
    Lists all keypoints that have keynote_number set.
    Shows the numbered list and allows assigning/clearing keynote numbers.

    Signals
    -------
    keynote_selected(keypoint_id_str)
    assign_keynote_requested(keypoint_id_str)
    clear_keynote_requested(keypoint_id_str)
    """

    keynote_selected = pyqtSignal(str)
    assign_keynote_requested = pyqtSignal(str)
    clear_keynote_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)

        title_row = QHBoxLayout()
        title = QLabel(t("Key Points"))
        title.setStyleSheet("font-weight: bold; padding: 2px;")
        title_row.addWidget(title, 1)
        title_row.addWidget(create_help_button(self, self._show_help))
        layout.addLayout(title_row)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        btns = QHBoxLayout()
        btn_assign = QPushButton(t("Assign #"))
        btn_assign.setToolTip(t("Assign the next number to the selected key point"))
        btn_assign.clicked.connect(self._on_assign)
        btn_clear = QPushButton(t("Clear #"))
        btn_clear.setToolTip(t("Clear the number from the selected key point"))
        btn_clear.clicked.connect(self._on_clear)
        btns.addWidget(btn_assign)
        btns.addWidget(btn_clear)
        layout.addLayout(btns)

    def _show_help(self) -> None:
        show_help_dialog(self, t("Panel Help"), t("Key Points panel help"))

    def refresh(self, project: Any) -> None:
        self._project = project
        self._list.clear()
        # Show all keypoints, keynoted ones with their number
        keypointed = sorted(
            [k for k in project.keypoints if k.keynote_number is not None],
            key=lambda k: k.keynote_number,
        )
        for kp in keypointed:
            label = f"  {kp.keynote_number}. {kp.info_card.title or 'Pin'}"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, str(kp.id))
            self._list.addItem(it)

        # Also show non-keynoted points
        for kp in project.keypoints:
            if kp.keynote_number is None:
                label = f"  — {kp.info_card.title or 'Pin'}"
                it = QListWidgetItem(label)
                it.setData(Qt.ItemDataRole.UserRole, str(kp.id))
                self._list.addItem(it)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        kp_id = item.data(Qt.ItemDataRole.UserRole)
        if kp_id:
            self.keynote_selected.emit(kp_id)

    def _on_assign(self) -> None:
        selected = self._list.selectedItems()
        if selected:
            kp_id = selected[0].data(Qt.ItemDataRole.UserRole)
            if kp_id:
                self.assign_keynote_requested.emit(kp_id)

    def _on_clear(self) -> None:
        selected = self._list.selectedItems()
        if selected:
            kp_id = selected[0].data(Qt.ItemDataRole.UserRole)
            if kp_id:
                self.clear_keynote_requested.emit(kp_id)
