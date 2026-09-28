"""Element edit dialog — edit zone or keypoint attributes from the context menu."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QWidget,
)

from bimap.ui.panels.properties_panel import PropertiesPanel
from bimap.ui._utils import _set_nested_attr, add_dialog_help_button


class ElementEditDialog(QDialog):
    """
    Standalone dialog to edit a zone or keypoint's attributes.
    Opens with a deep-copy of the element so changes are not applied until
    the user clicks OK.

    Usage::

        dlg = ElementEditDialog(zone, "zone", project, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # dlg.element holds the modified copy; push an undo command with it
            pass
    """

    def __init__(
        self,
        element: Any,
        element_type: str,
        project: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._element = deepcopy(element)
        self._etype = element_type
        self.setWindowTitle(f"Edit {element_type.capitalize()}")
        self.setMinimumWidth(320)
        self._setup_ui(project)

    def _setup_ui(self, project: Any) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._props = PropertiesPanel()
        if project is not None:
            self._props.set_project(project)
        self._props.show_element(self._element, self._etype)
        # Apply changes to the local deep-copy in real time
        self._props.element_changed.connect(self._on_change)
        layout.addWidget(self._props)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        add_dialog_help_button(buttons, self, "Element Editor window help")
        layout.addWidget(buttons)

    def _on_change(self, etype: str, eid: str, field: str, value: Any) -> None:
        try:
            _set_nested_attr(self._element, field, value)
        except (AttributeError, ValueError):
            pass

    @property
    def element(self) -> Any:
        """The (potentially modified) copy of the element after editing."""
        return self._element
