"""Form Designer dialog — create and edit FormDesign objects for the project."""

from __future__ import annotations

import copy
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button
from bimap.models.form_design import FieldType, FormDesign, FormField


def _make_general_info_form() -> FormDesign:
    """Return the pre-built General Information FormDesign template."""
    return FormDesign(
        name=t("General Information"),
        description=t("Standard general-purpose information form for zones and keypoints."),
        target="both",
        fields=[
            FormField(label=t("Name"), field_type=FieldType.TEXT, required=True, default_value=""),
            FormField(label=t("Description"), field_type=FieldType.TEXTAREA, default_value=""),
            FormField(label=t("Status"), field_type=FieldType.DROPDOWN,
                      options=[t("Active"), t("Inactive"), t("Pending"), t("Under Review")],
                      default_value=t("Active")),
            FormField(label=t("Priority"), field_type=FieldType.DROPDOWN,
                      options=[t("Low"), t("Medium"), t("High"), t("Critical")],
                      default_value=t("Medium")),
            FormField(label=t("Notes"), field_type=FieldType.TEXTAREA, default_value=""),
            FormField(label=t("Tags"), field_type=FieldType.TEXT, default_value=""),
            FormField(label=t("Date"), field_type=FieldType.DATE, default_value=""),
        ],
    )


class FormDesignerDialog(QDialog):
    """Full-screen dialog for managing the project's FormDesign library.

    Left column  — list of form designs (add / delete).
    Right column — name, description, target, and a field list editor.
    """

    def __init__(
        self,
        designs: list[FormDesign],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Form Designer"))
        self.resize(900, 620)
        self.designs: list[FormDesign] = copy.deepcopy(designs)
        self._current_idx: int = -1
        self._current_field_idx: int = -1
        self._setup_ui()
        if self.designs:
            self._list.setCurrentRow(0)
        else:
            self._set_editor_enabled(False)

    # ── UI construction ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ── Left: form list ───────────────────────────────────────────────── #
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        forms_header = QHBoxLayout()
        forms_title = QLabel(t("Forms"))
        forms_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        forms_header.addWidget(forms_title)
        self._forms_count = QLabel()
        self._forms_count.setStyleSheet("color: #888888;")
        forms_header.addWidget(self._forms_count)
        forms_header.addStretch()
        lv.addLayout(forms_header)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setSpacing(2)
        self._list.setToolTip(t("Select a form to edit its properties and fields"))
        self._list.currentRowChanged.connect(self._on_select)
        lv.addWidget(self._list, 1)

        for d in self.designs:
            item = QListWidgetItem(d.name)
            item.setData(Qt.ItemDataRole.UserRole, str(d.id))
            self._list.addItem(item)

        btn_new = QPushButton(t("+ New Form"))
        btn_new.setToolTip(t("Create a blank form"))
        btn_new.clicked.connect(self._new_design)
        btn_del = QPushButton(t("Delete"))
        btn_del.setToolTip(t("Delete the selected form"))
        btn_del.clicked.connect(self._delete_design)
        btn_gi = QPushButton(t("+ General Info"))
        btn_gi.setToolTip(t("Insert a pre-built General Information form with common fields"))
        btn_gi.clicked.connect(self._add_general_info_design)
        btnrow = QHBoxLayout()
        btnrow.addWidget(btn_new)
        btnrow.addWidget(btn_del)
        lv.addLayout(btnrow)
        lv.addWidget(btn_gi)
        left.setMinimumWidth(200)
        splitter.addWidget(left)

        # ── Right: design editor ──────────────────────────────────────────── #
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)

        # Header properties
        meta_grp = QGroupBox(t("Form Properties"))
        meta_form = QFormLayout(meta_grp)
        self._name_edit = QLineEdit()
        self._name_edit.textEdited.connect(self._on_name_changed)
        meta_form.addRow(t("Name"), self._name_edit)

        self._desc_edit = QLineEdit()
        self._desc_edit.textEdited.connect(self._on_desc_changed)
        meta_form.addRow(t("Description"), self._desc_edit)

        self._target_combo = QComboBox()
        for val, label in [("both", t("Zone & Keypoint")), ("zone", t("Zone")), ("keypoint", t("Keypoint"))]:
            self._target_combo.addItem(label, val)
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        self._target_combo.setToolTip(t("Choose which element types can use this form"))
        meta_form.addRow(t("Target"), self._target_combo)
        rv.addWidget(meta_grp)

        # Field list
        field_grp = QGroupBox(t("Fields"))
        field_layout = QVBoxLayout(field_grp)

        self._field_list = QListWidget()
        self._field_list.setAlternatingRowColors(True)
        self._field_list.setSpacing(2)
        self._field_list.setToolTip(t("Select a field to edit its settings"))
        self._field_list.currentRowChanged.connect(self._on_field_select)
        field_layout.addWidget(self._field_list, 1)

        field_btns = QHBoxLayout()
        btn_add_field = QPushButton(t("+ Add Field"))
        btn_add_field.setToolTip(t("Add a field to this form"))
        btn_add_field.clicked.connect(self._add_field)
        btn_del_field = QPushButton(t("Remove Field"))
        btn_del_field.setToolTip(t("Remove the selected field"))
        btn_del_field.clicked.connect(self._delete_field)
        btn_up = QPushButton("▲")
        btn_up.setToolTip(t("Move field up"))
        btn_up.setFixedSize(32, 28)
        btn_up.clicked.connect(self._move_field_up)
        btn_dn = QPushButton("▼")
        btn_dn.setToolTip(t("Move field down"))
        btn_dn.setFixedSize(32, 28)
        btn_dn.clicked.connect(self._move_field_down)
        field_btns.addWidget(btn_add_field)
        field_btns.addWidget(btn_del_field)
        field_btns.addStretch()
        field_btns.addWidget(btn_up)
        field_btns.addWidget(btn_dn)
        field_layout.addLayout(field_btns)

        # Field property editor
        self._field_editor = QGroupBox(t("Field Editor"))
        fe_form = QFormLayout(self._field_editor)

        self._fl_label = QLineEdit()
        self._fl_label.setPlaceholderText(t("Field label (used as metadata key)"))
        self._fl_label.textEdited.connect(self._on_field_label_changed)
        fe_form.addRow(t("Label"), self._fl_label)

        self._fl_type = QComboBox()
        for ft in FieldType:
            self._fl_type.addItem(ft.value.capitalize(), ft)
        self._fl_type.currentIndexChanged.connect(self._on_field_type_changed)
        fe_form.addRow(t("Type"), self._fl_type)

        self._fl_required = QCheckBox()
        self._fl_required.stateChanged.connect(self._on_field_required_changed)
        fe_form.addRow(t("Required"), self._fl_required)

        self._fl_default = QLineEdit()
        self._fl_default.setPlaceholderText(t("Default value"))
        self._fl_default.textEdited.connect(self._on_field_default_changed)
        fe_form.addRow(t("Default"), self._fl_default)

        self._fl_options_label = QLabel(t("Options (one per line):"))
        self._fl_options = QTextEdit()
        self._fl_options.setMinimumHeight(70)
        self._fl_options.setMaximumHeight(110)
        self._fl_options.setPlaceholderText("Option A\nOption B\nOption C")
        self._fl_options.textChanged.connect(self._on_field_options_changed)
        fe_form.addRow(self._fl_options_label)
        fe_form.addRow(self._fl_options)

        field_splitter = QSplitter(Qt.Orientation.Vertical)
        field_splitter.addWidget(field_grp)
        field_splitter.addWidget(self._field_editor)
        field_splitter.setStretchFactor(0, 3)
        field_splitter.setStretchFactor(1, 2)
        field_splitter.setSizes([260, 220])
        rv.addWidget(field_splitter, 1)

        # OK / Cancel
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        add_dialog_help_button(bbox, self, "Form Designer window help")
        rv.addWidget(bbox)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self._widgets_rhs: list[QWidget] = [meta_grp, field_grp, self._field_editor]
        self._field_editor.setEnabled(False)
        self._update_forms_count()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _set_editor_enabled(self, enabled: bool) -> None:
        for w in self._widgets_rhs:
            w.setEnabled(enabled)

    def _update_forms_count(self) -> None:
        self._forms_count.setText(f"({len(self.designs)})")

    def _reload_field_list(self) -> None:
        d = self._current_design
        if d is None:
            return
        self._field_list.blockSignals(True)
        self._field_list.clear()
        for f in d.fields:
            self._field_list.addItem(f"{f.label}  [{f.field_type}]")
        self._field_list.setProperty("empty", not bool(d.fields))
        self._field_list.blockSignals(False)

    @property
    def _current_design(self) -> FormDesign | None:
        if 0 <= self._current_idx < len(self.designs):
            return self.designs[self._current_idx]
        return None

    @property
    def _current_field(self) -> FormField | None:
        d = self._current_design
        if d and 0 <= self._current_field_idx < len(d.fields):
            return d.fields[self._current_field_idx]
        return None

    # ── Slots — form list ──────────────────────────────────────────────────────

    def _on_select(self, row: int) -> None:
        self._current_idx = row
        d = self._current_design
        if d is None:
            self._set_editor_enabled(False)
            return
        self._set_editor_enabled(True)
        self._name_edit.blockSignals(True)
        self._name_edit.setText(d.name)
        self._name_edit.blockSignals(False)
        self._desc_edit.setText(d.description)
        idx = self._target_combo.findData(d.target)
        self._target_combo.blockSignals(True)
        self._target_combo.setCurrentIndex(max(idx, 0))
        self._target_combo.blockSignals(False)
        self._reload_field_list()
        self._current_field_idx = -1
        self._field_editor.setEnabled(False)
        if d.fields:
            self._field_list.setCurrentRow(0)

    def _new_design(self) -> None:
        design = FormDesign(name=t("New Form"))
        self.designs.append(design)
        self._list.addItem(design.name)
        self._update_forms_count()
        self._list.setCurrentRow(len(self.designs) - 1)
        self._set_editor_enabled(True)
        self._name_edit.setFocus()
        self._name_edit.selectAll()

    def _add_general_info_design(self) -> None:
        """Insert the pre-built General Information form as a new design."""
        design = _make_general_info_form()
        self.designs.append(design)
        self._list.addItem(design.name)
        self._update_forms_count()
        self._list.setCurrentRow(len(self.designs) - 1)
        self._set_editor_enabled(True)

    def _delete_design(self) -> None:
        row = self._current_idx
        if row < 0 or row >= len(self.designs):
            return
        name = self.designs[row].name
        reply = QMessageBox.question(
            self, t("Confirm Delete"),
            t("Delete form '{name}'? This cannot be undone.").replace("{name}", name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del self.designs[row]
        self._list.takeItem(row)
        self._update_forms_count()
        self._current_idx = -1
        if self.designs:
            self._list.setCurrentRow(min(row, len(self.designs) - 1))
        else:
            self._set_editor_enabled(False)

    def _on_name_changed(self, text: str) -> None:
        d = self._current_design
        if d:
            d.name = text
            item = self._list.item(self._current_idx)
            if item:
                item.setText(text)

    def _on_desc_changed(self, text: str) -> None:
        d = self._current_design
        if d:
            d.description = text

    def _on_target_changed(self) -> None:
        d = self._current_design
        if d:
            d.target = self._target_combo.currentData() or "both"

    # ── Slots — field list ─────────────────────────────────────────────────────

    def _on_field_select(self, row: int) -> None:
        self._current_field_idx = row
        f = self._current_field
        if f is None:
            self._field_editor.setEnabled(False)
            return
        self._field_editor.setEnabled(True)
        self._fl_label.blockSignals(True)
        self._fl_label.setText(f.label)
        self._fl_label.blockSignals(False)
        # Type combo
        self._fl_type.blockSignals(True)
        for i in range(self._fl_type.count()):
            if self._fl_type.itemData(i) == f.field_type:
                self._fl_type.setCurrentIndex(i)
                break
        self._fl_type.blockSignals(False)
        self._fl_required.blockSignals(True)
        self._fl_required.setChecked(f.required)
        self._fl_required.blockSignals(False)
        self._fl_default.blockSignals(True)
        self._fl_default.setText(f.default_value)
        self._fl_default.blockSignals(False)
        self._fl_options.blockSignals(True)
        self._fl_options.setPlainText("\n".join(f.options))
        self._fl_options.blockSignals(False)
        is_dropdown = f.field_type == FieldType.DROPDOWN
        self._fl_options.setEnabled(is_dropdown)
        self._fl_options_label.setEnabled(is_dropdown)

    def _add_field(self) -> None:
        d = self._current_design
        if d is None:
            return
        field = FormField(label=t("New Field"))
        d.fields.append(field)
        self._reload_field_list()
        self._field_list.setCurrentRow(len(d.fields) - 1)

    def _delete_field(self) -> None:
        d = self._current_design
        row = self._current_field_idx
        if d is None or row < 0 or row >= len(d.fields):
            return
        del d.fields[row]
        self._reload_field_list()
        self._current_field_idx = -1
        self._field_editor.setEnabled(False)

    def _move_field_up(self) -> None:
        d = self._current_design
        i = self._current_field_idx
        if d and 0 < i < len(d.fields):
            d.fields[i - 1], d.fields[i] = d.fields[i], d.fields[i - 1]
            self._reload_field_list()
            self._field_list.setCurrentRow(i - 1)

    def _move_field_down(self) -> None:
        d = self._current_design
        i = self._current_field_idx
        if d and 0 <= i < len(d.fields) - 1:
            d.fields[i], d.fields[i + 1] = d.fields[i + 1], d.fields[i]
            self._reload_field_list()
            self._field_list.setCurrentRow(i + 1)

    def _on_field_label_changed(self, text: str) -> None:
        f = self._current_field
        if f:
            f.label = text
            self._reload_field_list()
            self._field_list.setCurrentRow(self._current_field_idx)

    def _on_field_type_changed(self) -> None:
        f = self._current_field
        if f:
            f.field_type = self._fl_type.currentData()
            is_dropdown = f.field_type == FieldType.DROPDOWN
            self._fl_options.setEnabled(is_dropdown)
            self._fl_options_label.setEnabled(is_dropdown)
            self._reload_field_list()
            self._field_list.setCurrentRow(self._current_field_idx)

    def _on_field_required_changed(self) -> None:
        f = self._current_field
        if f:
            f.required = self._fl_required.isChecked()

    def _on_field_default_changed(self, text: str) -> None:
        f = self._current_field
        if f:
            f.default_value = text

    def _on_field_options_changed(self) -> None:
        f = self._current_field
        if f:
            raw = self._fl_options.toPlainText()
            f.options = [o.strip() for o in raw.splitlines() if o.strip()]
