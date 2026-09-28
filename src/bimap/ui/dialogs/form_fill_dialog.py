"""Form Fill dialog — render a FormDesign as a fill-in form and save values to element metadata."""

from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.models.form_design import FieldType, FormDesign
from bimap.ui._utils import add_dialog_help_button


class FormFillDialog(QDialog):
    """Dynamic fill-in dialog rendered from a *FormDesign*.

    On accept or on each widget change (when *on_change* is supplied), the
    values are written back to *element.metadata* using each field's *label*
    as the key so they appear in the Properties panel as readable attributes.

    Parameters
    ----------
    on_change:
        Optional callable called with ``(element, field_label, new_value)``
        whenever any widget value changes — enables live metadata updates.
    """

    def __init__(
        self,
        form: FormDesign,
        element: Any,
        etype: str,
        parent: QWidget | None = None,
        on_change: Callable[[Any, str, str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(form.name)
        self._form = form
        self._element = element
        self._on_change = on_change
        self._widgets: dict[str, QWidget] = {}
        self._setup_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        vbox = QVBoxLayout(self)

        if self._form.description:
            desc = QLabel(self._form.description)
            desc.setWordWrap(True)
            vbox.addWidget(desc)

        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        vbox.addLayout(form_layout)

        meta = getattr(self._element, "metadata", {}) or {}

        for field in self._form.fields:
            existing = meta.get(field.label, field.default_value)
            widget = self._make_widget(field, existing)
            self._widgets[field.label] = widget
            label_text = field.label
            if field.required:
                label_text += " *"
            form_layout.addRow(label_text, widget)
            # Wire live-update signal for each widget type
            if self._on_change is not None:
                self._wire_live_update(field, widget)

        if any(f.required for f in self._form.fields):
            vbox.addWidget(QLabel(t("* Required fields")))

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._on_accept)
        bbox.rejected.connect(self.reject)
        add_dialog_help_button(bbox, self, "Form Fill window help")
        vbox.addWidget(bbox)

        self.resize(440, max(200, 80 + len(self._form.fields) * 36))

    def _make_widget(self, field: Any, current_value: str) -> QWidget:
        ft = field.field_type
        if ft == FieldType.TEXT:
            w = QLineEdit()
            w.setText(str(current_value))
            return w
        if ft == FieldType.NUMBER:
            w = QDoubleSpinBox()
            w.setRange(-1e12, 1e12)
            w.setDecimals(4)
            w.setSingleStep(1.0)
            try:
                w.setValue(float(current_value))
            except (ValueError, TypeError):
                w.setValue(0.0)
            return w
        if ft == FieldType.DROPDOWN:
            w = QComboBox()
            for opt in field.options:
                w.addItem(opt)
            if current_value in field.options:
                w.setCurrentText(current_value)
            elif field.options:
                w.setCurrentIndex(0)
            return w
        if ft == FieldType.CHECKBOX:
            w = QCheckBox()
            w.setChecked(str(current_value).lower() in ("true", "1", "yes"))
            return w
        if ft == FieldType.DATE:
            w = QDateEdit()
            w.setCalendarPopup(True)
            if current_value:
                d = QDate.fromString(str(current_value), "yyyy-MM-dd")
                if d.isValid():
                    w.setDate(d)
                else:
                    w.setDate(QDate.currentDate())
            else:
                w.setDate(QDate.currentDate())
            return w
        if ft == FieldType.TEXTAREA:
            w = QTextEdit()
            w.setPlainText(str(current_value))
            w.setMaximumHeight(100)
            return w
        # fallback
        w = QLineEdit()
        w.setText(str(current_value))
        return w

    def _read_widget(self, field: Any) -> str:
        w = self._widgets.get(field.label)
        if w is None:
            return ""
        ft = field.field_type
        if ft == FieldType.TEXT:
            return w.text()
        if ft == FieldType.NUMBER:
            return str(w.value())
        if ft == FieldType.DROPDOWN:
            return w.currentText()
        if ft == FieldType.CHECKBOX:
            return "true" if w.isChecked() else "false"
        if ft == FieldType.DATE:
            return w.date().toString("yyyy-MM-dd")
        if ft == FieldType.TEXTAREA:
            return w.toPlainText()
        return ""

    def _wire_live_update(self, field: Any, widget: QWidget) -> None:
        """Connect the widget's change signal to immediately update element.metadata."""
        ft = field.field_type
        el = self._element
        lbl = field.label

        def _apply(val: str) -> None:
            if not hasattr(el, "metadata") or el.metadata is None:
                el.metadata = {}
            el.metadata[lbl] = val
            if self._on_change is not None:
                self._on_change(el, lbl, val)

        if ft == FieldType.TEXT:
            widget.textChanged.connect(lambda v: _apply(v))
        elif ft == FieldType.NUMBER:
            widget.valueChanged.connect(lambda v: _apply(str(v)))
        elif ft == FieldType.DROPDOWN:
            widget.currentTextChanged.connect(lambda v: _apply(v))
        elif ft == FieldType.CHECKBOX:
            widget.toggled.connect(lambda v: _apply("true" if v else "false"))
        elif ft == FieldType.DATE:
            widget.dateChanged.connect(
                lambda d: _apply(d.toString("yyyy-MM-dd"))
            )
        elif ft == FieldType.TEXTAREA:
            widget.textChanged.connect(
                lambda: _apply(widget.toPlainText())
            )

    # ── Slot ──────────────────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        # Validate required fields
        for field in self._form.fields:
            if field.required:
                val = self._read_widget(field)
                if not val.strip():
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self,
                        t("Required Field"),
                        t("Field '{label}' is required.").replace("{label}", field.label),
                    )
                    return

        # Write to metadata
        if not hasattr(self._element, "metadata") or self._element.metadata is None:
            self._element.metadata = {}
        for field in self._form.fields:
            self._element.metadata[field.label] = self._read_widget(field)

        self.accept()
