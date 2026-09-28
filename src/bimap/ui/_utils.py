"""Shared UI utility helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
    QTextBrowser,
    QToolButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t


def _set_nested_attr(obj: Any, dotted_path: str, value: Any) -> None:
    """Set a nested attribute like 'style.fill_color' on *obj*."""
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        if part == "info_card" and hasattr(obj, "info_card"):
            obj = obj.info_card
        elif part == "style" and hasattr(obj, "style"):
            obj = obj.style
        elif part == "label" and hasattr(obj, "label"):
            obj = obj.label
        elif part == "fields":
            return  # complex sub-list, skip for now
        else:
            obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def ask_question(
    parent: Any,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton,
    default: QMessageBox.StandardButton,
) -> QMessageBox.StandardButton:
    """Show a question dialog with application-language button captions."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(buttons)
    box.setDefaultButton(default)
    captions = {
        QMessageBox.StandardButton.Yes: "Yes",
        QMessageBox.StandardButton.No: "No",
        QMessageBox.StandardButton.Cancel: "Cancel",
        QMessageBox.StandardButton.Ok: "OK",
    }
    for button, caption in captions.items():
        widget = box.button(button)
        if widget is not None:
            widget.setText(t(caption))
    box.exec()
    return box.standardButton(box.clickedButton())


def create_help_button(
    parent: QWidget,
    callback: Callable[[], None],
    tooltip_key: str = "Open help for this panel",
) -> QToolButton:
    """Return a compact, theme-visible question-mark button."""
    button = QToolButton(parent)
    button.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
    button.setAutoRaise(True)
    button.setToolTip(t(tooltip_key))
    button.clicked.connect(lambda _checked=False: callback())
    return button


def show_help_dialog(parent: QWidget, title: str, html: str) -> None:
    """Show localized rich-text help with a consistent close action."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(560, 430)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser()
    browser.setOpenExternalLinks(False)
    browser.setHtml(html)
    layout.addWidget(browser)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()


def add_dialog_help_button(
    button_box: QDialogButtonBox,
    parent: QWidget,
    help_key: str,
) -> None:
    """Add an icon-only help button to a dialog button box."""
    button = create_help_button(
        parent,
        lambda: show_help_dialog(parent, t("Application Help"), t(help_key)),
        "Open help for this window",
    )
    layout = parent.layout()
    if layout is None:
        button_box.addButton(button, QDialogButtonBox.ButtonRole.ActionRole)
        return
    header = QHBoxLayout()
    header.addStretch()
    header.addWidget(button)
    layout.insertLayout(0, header)


def add_top_right_help_button(
    dialog: QDialog,
    callback: Callable[[], None],
) -> None:
    """Add an icon-only window-help button in the dialog's top-right corner."""
    button = create_help_button(dialog, callback, "Open help for this window")
    layout = dialog.layout()
    if layout is None:
        return
    header = QHBoxLayout()
    header.addStretch()
    header.addWidget(button)
    layout.insertLayout(0, header)
