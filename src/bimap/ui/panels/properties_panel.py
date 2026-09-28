"""Properties panel — edit properties of the currently selected element."""

from __future__ import annotations

import math
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator, QFont, QIntValidator
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.models.annotation import Annotation
from bimap.models.keypoint import Keypoint
from bimap.models.zone import Zone, ZoneType
from bimap.ui.widgets import ColorButton
from bimap.ui._utils import ask_question, create_help_button, show_help_dialog


def _hav_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres between two WGS-84 coordinate pairs."""
    R = 6_371_000.0
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(1.0, a)))


class PropertiesPanel(QWidget):
    """
    Dynamic panel showing editable properties for the selected element.

    Signals
    -------
    element_changed(element_type, element_id, field, value) — a field was edited
    """

    element_changed = pyqtSignal(str, str, str, object)
    # Emitted when user applies a style preset: (element_type, element_id, preset_name)
    preset_applied = pyqtSignal(str, str, str)
    # Emitted when a metadata key-value pair changes: (element_type, element_id, key, value|None)
    metadata_changed = pyqtSignal(str, str, str, object)
    # Emitted when visibility of a metadata key changes: (element_type, element_id, hidden_keys_list)
    metadata_hidden_changed = pyqtSignal(str, str, list)
    # Emitted when a metadata binding changes: (element_type, element_id, key, binding|None)
    metadata_binding_changed = pyqtSignal(str, str, str, object)
    # Emitted when the user clicks "Open Form Designer" from the properties panel
    open_form_designer_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._element: Any = None
        self._etype: str = ""
        self._project: Any = None
        self._rebuilding: bool = False  # True while form is being torn down/rebuilt
        self._setup_ui()

    def set_project(self, project: Any) -> None:
        """Supply the current project so presets can be listed."""
        self._project = project

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 6, 4, 4)
        outer.setSpacing(4)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel(t("Properties"))
        self._title.setStyleSheet(
            "font-weight: bold; font-size: 12px;"
            "padding: 3px 4px;"
            "background: #252526;"
            "color: #9CDCFE;"
            "border-bottom: 1px solid #3C3C3C;"
        )
        header_layout.addWidget(self._title, 1)
        self._help_button = create_help_button(self, self._show_help)
        header_layout.addWidget(self._help_button)
        outer.addWidget(header)

        # ── Tab widget ──────────────────────────────────────────────────────── #
        self._tabs = QTabWidget()
        outer.addWidget(self._tabs)

        # Tab 0: Style (scroll area wrapping the form)
        style_tab = QWidget()
        style_vbox = QVBoxLayout(style_tab)
        style_vbox.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        style_vbox.addWidget(scroll)

        self._content = QWidget()
        self._form = QFormLayout(self._content)
        self._form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._form.setVerticalSpacing(6)
        self._form.setContentsMargins(4, 4, 4, 4)
        self._content.setStyleSheet(
            "QGroupBox {"
            "  font-weight: bold;"
            "  font-size: 11px;"
            "  border: 1px solid #3C3C3C;"
            "  border-radius: 4px;"
            "  margin-top: 8px;"
            "  padding-top: 4px;"
            "}"
            "QGroupBox::title {"
            "  subcontrol-origin: margin;"
            "  subcontrol-position: top left;"
            "  padding: 0 4px;"
            "  color: #AAAAAA;"
            "}"
        )
        scroll.setWidget(self._content)

        # Tab 1: Metadata (direct layout, no extra scroll needed)
        self._meta_tab = QWidget()
        self._meta_layout = QVBoxLayout(self._meta_tab)
        self._meta_layout.setContentsMargins(6, 6, 6, 6)
        self._meta_layout.setSpacing(6)
        _empty = QLabel("Select an element to view its metadata.")
        _empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _empty.setStyleSheet("color: #888888; font-style: italic;")
        self._meta_layout.addWidget(_empty)
        self._meta_layout.addStretch()

        self._tabs.addTab(style_tab, t("Style"))
        self._tabs.addTab(self._meta_tab, t("Metadata"))

    def show_element(self, element: Any, etype: str) -> None:
        self._rebuilding = True
        self._element = element
        self._etype = etype
        self._clear_form()
        if etype == "zone":
            self._populate_zone(element)
        elif etype == "keypoint":
            self._populate_keypoint(element)
        elif etype == "annotation":
            self._populate_annotation(element)
        elif etype == "data_feature":
            self._populate_data_feature(element)
        # Always reveal the Style tab so the user sees content immediately
        self._tabs.setCurrentIndex(0)
        self._rebuilding = False

    def refresh_current(self) -> None:
        """Re-render the panel for the currently displayed element (e.g. after undo/redo).

        Always looks up the **fresh** copy of the element from the project so
        that the panel reflects the actual model state even after undo commands
        replace the project's zone/keypoint list entries with deep-copies.
        """
        if self._element is None:
            return
        # Don't rebuild while the user is actively editing a field inside this
        # panel — a continuous signal (e.g. slider valueChanged) could otherwise
        # tear down and recreate the form mid-keystroke, resetting the value.
        focused = QApplication.focusWidget()
        if focused is not None and self.isAncestorOf(focused):
            return
        element = self._element
        if self._project is not None:
            element = self._find_in_project(self._etype, self._element.id) or element
        self.show_element(element, self._etype)

    def _find_in_project(self, etype: str, element_id: object) -> Any:
        """Return the live project object matching *etype* and *element_id*, or None."""
        if self._project is None:
            return None
        if etype == "zone":
            return next((z for z in self._project.zones if z.id == element_id), None)
        if etype == "keypoint":
            return next((k for k in self._project.keypoints if k.id == element_id), None)
        if etype == "annotation":
            return next((a for a in self._project.annotations if a.id == element_id), None)
        return None

    def clear(self) -> None:
        self._element = None
        self._etype = ""
        self._clear_form()
        self._title.setText(t("Properties"))

    def _show_help(self) -> None:
        """Show a guide for the currently selected element type."""
        help_key = {
            "zone": "Properties help for zones",
            "keypoint": "Properties help for key points",
            "annotation": "Properties help for annotations",
            "data_feature": "Properties help for data features",
        }.get(self._etype, "Properties help with no selection")
        show_help_dialog(self, t("Properties Help"), t(help_key))

    # ── Form builders ──────────────────────────────────────────────────────────

    def _clear_form(self) -> None:
        # Block signals on all child widgets before removing them so that
        # QDoubleSpinBox / QLineEdit don't fire editingFinished during teardown
        # and accidentally overwrite the value the user just committed.
        for i in range(self._form.rowCount()):
            for role in (QFormLayout.ItemRole.LabelRole, QFormLayout.ItemRole.FieldRole):
                item = self._form.itemAt(i, role)
                if item and item.widget():
                    item.widget().blockSignals(True)
        while self._form.rowCount() > 0:
            self._form.removeRow(0)
        # Clear metadata tab content
        while self._meta_layout.count() > 0:
            item = self._meta_layout.takeAt(0)
            if item.widget():
                item.widget().blockSignals(True)
                item.widget().deleteLater()

    def _populate_zone(self, zone: "Zone") -> None:
        # Determine display width/height (may need to compute from coords for new zones)
        _coords = list(zone.coordinates or [])
        _w = zone.width_m
        _h = zone.height_m
        if zone.zone_type == ZoneType.RECTANGLE and len(_coords) >= 4:
            if _w == 0:
                _w = _hav_m(_coords[0].lat, _coords[0].lon, _coords[1].lat, _coords[1].lon)
            if _h == 0:
                _h = _hav_m(_coords[1].lat, _coords[1].lon, _coords[2].lat, _coords[2].lon)

        if _w > 0 and _h > 0:
            dim = f" ({_w:.1f}×{_h:.1f} m)"
        else:
            dim = ""
        self._title.setText(f"{t('Zone')}: {zone.name}{dim}")

        # Style presets (only shown if the project has any)
        presets = getattr(self._project, "style_presets", []) if self._project else []
        if presets:
            preset_combo = QComboBox()
            preset_combo.addItem(t("— Apply Preset —"))
            preset_combo.setToolTip(t("Apply a saved style to this zone"))
            for p in presets:
                preset_combo.addItem(p.name)
            preset_combo.currentIndexChanged.connect(
                lambda idx: (
                    self.preset_applied.emit(self._etype, str(zone.id), presets[idx - 1].name)
                    if idx > 0 and self._element
                    else None
                )
            )
            self._form.addRow(t("Preset"), preset_combo)
        name_edit = self._add_line_edit(t("Name"), zone.name)

        def _name_changed() -> None:
            value = name_edit.text()
            self._emit("name", value)
            if value != zone.label.text and ask_question(
                self,
                t("Update label text?"),
                t("Update the label text to match the new name?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            ) == QMessageBox.StandardButton.Yes:
                self._emit("label.text", value)

        name_edit.editingFinished.connect(
            _name_changed
        )
        group_edit = self._add_line_edit(t("Group"), zone.group)
        group_edit.editingFinished.connect(
            lambda: self._emit("group", group_edit.text())
        )

        # Style section
        bg = QGroupBox(t("Fill"))
        bg_layout = QFormLayout(bg)
        fill_btn = ColorButton(zone.style.fill_color)
        fill_btn.setToolTip(t("Fill color used inside the zone"))
        fill_btn.color_changed.connect(lambda c: self._emit("style.fill_color", c))
        bg_layout.addRow(t("Color"), fill_btn)

        alpha_slider = QSlider(Qt.Orientation.Horizontal)
        alpha_slider.setRange(0, 255)
        alpha_slider.setValue(zone.style.fill_alpha)
        alpha_slider.setToolTip(t("Fill opacity from transparent to opaque"))
        alpha_slider.valueChanged.connect(lambda v: self._emit("style.fill_alpha", v))
        bg_layout.addRow(t("Opacity"), alpha_slider)
        self._form.addRow(bg)

        border_grp = QGroupBox(t("Border"))
        border_layout = QFormLayout(border_grp)
        border_btn = ColorButton(zone.style.border_color)
        border_btn.setToolTip(t("Color of the zone border"))
        border_btn.color_changed.connect(lambda c: self._emit("style.border_color", c))
        border_layout.addRow(t("Color"), border_btn)
        bw_edit = QLineEdit(str(zone.style.border_width))
        bw_edit.setValidator(QIntValidator(0, 20, bw_edit))
        bw_edit.setToolTip(t("Border width in pixels (0 to 20)"))
        bw_edit.editingFinished.connect(
            lambda: self._emit("style.border_width", int(bw_edit.text() or "0"))
        )
        border_layout.addRow(t("Width"), bw_edit)
        self._form.addRow(border_grp)

        label_grp = QGroupBox(t("Label"))
        label_layout = QFormLayout(label_grp)
        label_grp.setEnabled(True)  # allow text entry even when empty

        lbl_edit = QLineEdit(zone.label.text)

        def _label_changed() -> None:
            value = lbl_edit.text()
            self._emit("label.text", value)
            if value != zone.name and ask_question(
                self,
                t("Update name?"),
                t("Update the name to match the new label text?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            ) == QMessageBox.StandardButton.Yes:
                self._emit("name", value)

        lbl_edit.editingFinished.connect(
            _label_changed
        )
        name_edit.setToolTip(t("Element name; changing it can also update the label text"))
        lbl_edit.setToolTip(t("Visible label text; changing it can also update the element name"))
        label_layout.addRow(t("Text"), lbl_edit)

        font_combo = QFontComboBox()
        font_combo.setToolTip(t("Choose the font family used by the label"))
        font_combo.setCurrentFont(QFont(zone.label.style.font_family))
        font_combo.currentFontChanged.connect(
            lambda f: self._emit("label.style.font_family", f.family())
        )
        label_layout.addRow(t("Font"), font_combo)

        fs_edit = QLineEdit(str(zone.label.style.font_size))
        fs_edit.setValidator(QIntValidator(6, 72, fs_edit))
        fs_edit.setToolTip(t("Label font size in points (6 to 72)"))
        fs_edit.editingFinished.connect(
            lambda: self._emit("label.style.font_size", int(fs_edit.text() or "12"))
        )
        label_layout.addRow(t("Size"), fs_edit)

        style_row_widget = QWidget()
        style_row = QHBoxLayout(style_row_widget)
        style_row.setContentsMargins(0, 0, 0, 0)
        bold_cb = QCheckBox(t("Bold"))
        bold_cb.setToolTip(t("Make the label text bold"))
        bold_cb.setChecked(zone.label.style.bold)
        bold_cb.toggled.connect(lambda v: self._emit("label.style.bold", v))
        italic_cb = QCheckBox(t("Italic"))
        italic_cb.setToolTip(t("Make the label text italic"))
        italic_cb.setChecked(zone.label.style.italic)
        italic_cb.toggled.connect(lambda v: self._emit("label.style.italic", v))
        style_row.addWidget(bold_cb)
        style_row.addWidget(italic_cb)
        label_layout.addRow(t("Style"), style_row_widget)

        txt_color_btn = ColorButton(zone.label.style.color)
        txt_color_btn.setToolTip(t("Label text color"))
        txt_color_btn.color_changed.connect(lambda c: self._emit("label.style.color", c))
        label_layout.addRow(t("Color"), txt_color_btn)

        bg_color_btn = ColorButton(zone.label.style.background_color or "#FFFFFF")
        bg_color_btn.setToolTip(t("Background color behind the label text"))
        bg_color_btn.color_changed.connect(
            lambda c: self._emit("label.style.background_color", c)
        )
        label_layout.addRow(t("Bg Color"), bg_color_btn)

        ox_edit = QLineEdit(str(zone.label.offset_x))
        ox_edit.setValidator(QDoubleValidator(-200.0, 200.0, 1, ox_edit))
        ox_edit.setToolTip(t("Horizontal label offset in pixels; positive values move right"))
        ox_edit.editingFinished.connect(
            lambda: self._emit("label.offset_x", float((ox_edit.text() or "0").replace(",", ".")))
        )
        label_layout.addRow(t("Offset X"), ox_edit)

        oy_edit = QLineEdit(str(zone.label.offset_y))
        oy_edit.setValidator(QDoubleValidator(-200.0, 200.0, 1, oy_edit))
        oy_edit.setToolTip(t("Vertical label offset in pixels; positive values move down"))
        oy_edit.editingFinished.connect(
            lambda: self._emit("label.offset_y", float((oy_edit.text() or "0").replace(",", ".")))
        )
        label_layout.addRow(t("Offset Y"), oy_edit)

        self._form.addRow(label_grp)

        # ── Geometry (metre-based sizing) ────────────────────────────────── #
        geo_grp = QGroupBox(t("Geometry"))
        geo_layout = QFormLayout(geo_grp)
        if zone.zone_type == ZoneType.CIRCLE:
            r_edit = QLineEdit(f"{zone.radius_m:.1f}")
            r_edit.setValidator(QDoubleValidator(1.0, 500_000.0, 1, r_edit))
            r_edit.setToolTip(t("Circle radius in metres"))
            r_edit.editingFinished.connect(
                lambda: self._emit("radius_m", float((r_edit.text() or "1").replace(",", ".")))
            )
            geo_layout.addRow(t("Radius (m)"), r_edit)
        elif zone.zone_type == ZoneType.RECTANGLE:
            w_edit = QLineEdit(f"{max(_w, 1.0):.1f}")
            w_edit.setValidator(QDoubleValidator(1.0, 500_000.0, 1, w_edit))
            w_edit.setToolTip(t("Rectangle width in metres"))
            w_edit.editingFinished.connect(
                lambda: self._emit("width_m", float((w_edit.text() or "1").replace(",", ".")))
            )
            geo_layout.addRow(t("Width (m)"), w_edit)

            h_edit = QLineEdit(f"{max(_h, 1.0):.1f}")
            h_edit.setValidator(QDoubleValidator(1.0, 500_000.0, 1, h_edit))
            h_edit.setToolTip(t("Rectangle height in metres"))
            h_edit.editingFinished.connect(
                lambda: self._emit("height_m", float((h_edit.text() or "1").replace(",", ".")))
            )
            geo_layout.addRow(t("Height (m)"), h_edit)
        # Rotation (all non-circle zone types)
        if zone.zone_type != ZoneType.CIRCLE:
            rot_edit = QLineEdit(f"{zone.rotation_deg:.1f}")
            rot_edit.setValidator(QDoubleValidator(-360.0, 360.0, 1, rot_edit))
            rot_edit.setToolTip(t("Rotate the zone in degrees clockwise"))
            rot_edit.editingFinished.connect(
                lambda: self._emit("rotation_deg", float((rot_edit.text() or "0").replace(",", ".")))
            )
            geo_layout.addRow(t("Rotation (°)"), rot_edit)
        self._form.addRow(geo_grp)

        # ── SVG Fill ─────────────────────────────────────────────────────── #
        svg_grp = QGroupBox(t("SVG Fill"))
        svg_layout = QFormLayout(svg_grp)

        svg_label = QLabel(zone.svg_fill_url or t("No file selected"))
        svg_label.setWordWrap(True)
        svg_label.setStyleSheet("color: #858585; font-size: 11px;")

        def _browse_svg() -> None:
            path, _ = QFileDialog.getOpenFileName(
                self, t("SVG Fill"), "", "SVG Files (*.svg);;All Files (*)"
            )
            if path:
                svg_label.setText(path)
                self._emit("svg_fill_url", path)

        def _clear_svg() -> None:
            svg_label.setText(t("No file selected"))
            self._emit("svg_fill_url", "")

        btn_row_widget = QWidget()
        btn_row_layout = QHBoxLayout(btn_row_widget)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        browse_btn = QPushButton(t("Browse\u2026"))
        browse_btn.setToolTip(t("Choose an SVG file to use as the zone fill"))
        browse_btn.clicked.connect(_browse_svg)
        clear_btn = QPushButton(t("Clear"))
        clear_btn.setToolTip(t("Remove the SVG fill from the zone"))
        clear_btn.clicked.connect(_clear_svg)
        btn_row_layout.addWidget(browse_btn)
        btn_row_layout.addWidget(clear_btn)
        btn_row_layout.addStretch()

        svg_layout.addRow(svg_label)
        svg_layout.addRow(btn_row_widget)
        self._form.addRow(svg_grp)

        # ── Linked Form Design ─────────────────────────────────────────────── #
        self._add_form_design_picker(zone, "zone")

        self._setup_metadata_tab(zone.metadata, zone)

    def _setup_metadata_tab(self, metadata: dict, element: Any) -> None:
        """Populate the Metadata tab with an editable key-value table."""
        # Clear existing tab content first
        while self._meta_layout.count() > 0:
            item = self._meta_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        hidden: list = list(getattr(element, "metadata_hidden", []))
        bindings: dict = dict(getattr(element, "metadata_bindings", {}))

        # 4 columns: Key | Value | 👁 | Source
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels([t("Key"), t("Value"), "👁", t("Source")])
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.resizeSection(0, 120)
        hdr.resizeSection(1, 120)
        hdr.resizeSection(2, 28)
        hdr.setSectionResizeMode(1, hdr.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, hdr.ResizeMode.ResizeToContents)
        table.setAlternatingRowColors(True)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setToolTip(t("Double-click Source column to bind a key to a data source"))

        def _source_label(key: str) -> str:
            b = bindings.get(key)
            if not b:
                return "—"
            sid = getattr(b, "source_id", "")
            col = getattr(b, "column", "")
            if self._project:
                for ds in getattr(self._project, "data_sources", []):
                    if str(ds.id) == sid:
                        return f"{ds.name} › {col}"
            return f"{sid[:8]}… › {col}"

        def _load() -> None:
            table.blockSignals(True)
            table.setRowCount(0)
            for k, v in metadata.items():
                row = table.rowCount()
                table.insertRow(row)
                # Col 0 – Key
                table.setItem(row, 0, QTableWidgetItem(k))
                # Col 1 – Value
                table.setItem(row, 1, QTableWidgetItem(v))
                # Col 2 – 👁 visible checkbox
                vis_item = QTableWidgetItem()
                vis_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                vis_item.setCheckState(
                    Qt.CheckState.Unchecked if k in hidden else Qt.CheckState.Checked
                )
                table.setItem(row, 2, vis_item)
                # Col 3 – Source binding (display only; double-click to edit)
                src_item = QTableWidgetItem(_source_label(k))
                src_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                src_item.setForeground(
                    table.palette().color(table.palette().ColorRole.Highlight)
                    if bindings.get(k) else table.palette().color(table.palette().ColorRole.PlaceholderText)
                )
                table.setItem(row, 3, src_item)
            table.blockSignals(False)

        _load()

        def _on_cell_changed(r: int, c: int) -> None:
            k_item = table.item(r, 0)
            if k_item is None:
                return
            key = k_item.text().strip()
            if not key:
                return
            if c in (0, 1):
                v_item = table.item(r, 1)
                val = v_item.text() if v_item else ""
                self.metadata_changed.emit(self._etype, str(element.id), key, val)
            elif c == 2:
                vis_item = table.item(r, 2)
                if vis_item is None:
                    return
                is_hidden = vis_item.checkState() == Qt.CheckState.Unchecked
                if is_hidden and key not in hidden:
                    hidden.append(key)
                elif not is_hidden and key in hidden:
                    hidden.remove(key)
                self.metadata_hidden_changed.emit(self._etype, str(element.id), list(hidden))

        table.cellChanged.connect(_on_cell_changed)

        def _on_cell_double_clicked(r: int, c: int) -> None:
            if c != 3:
                return
            k_item = table.item(r, 0)
            if k_item is None:
                return
            key = k_item.text().strip()
            if not key:
                return
            _open_binding_dialog(key, r)

        def _open_binding_dialog(key: str, row: int) -> None:
            sources = getattr(self._project, "data_sources", []) if self._project else []
            dlg = QDialog(self)
            dlg.setWindowTitle(t("Bind Metadata Key") + f" — {key}")
            dlg.resize(400, 280)
            main_v = QVBoxLayout(dlg)
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

            # Data source combo
            _NEW_DS_SENTINEL = "__new__"
            src_combo = QComboBox()
            src_combo.setToolTip(t("Choose the data source that provides values for this metadata key"))
            src_combo.addItem(t("— none —"), "")
            for ds in sources:
                src_combo.addItem(ds.name, str(ds.id))
            src_combo.addItem(t("➕ New Data Source…"), _NEW_DS_SENTINEL)
            cur_binding = bindings.get(key)
            cur_sid = getattr(cur_binding, "source_id", "") if cur_binding else ""
            idx = src_combo.findData(cur_sid)
            src_combo.setCurrentIndex(max(0, idx))

            def _on_src_combo_changed(index: int, _combo=src_combo) -> None:
                if _combo.itemData(index) != _NEW_DS_SENTINEL:
                    return
                # Open new data source wizard; if accepted, add to project and select it
                try:
                    from bimap.ui.dialogs.data_source_dialog import DataSourceDialog
                    from bimap.data.base import build_connector
                    from bimap.engine.commands import AddDataSourceCommand
                except ImportError:
                    _combo.setCurrentIndex(0)
                    return
                new_dlg = DataSourceDialog(parent=dlg)
                if new_dlg.exec():
                    new_ds = new_dlg.source
                    try:
                        connector = build_connector(new_ds)
                        connector.connect()
                    except Exception:
                        connector = None
                    if self._project is not None:
                        self._project.data_sources.append(new_ds)
                    _combo.insertItem(_combo.count() - 1, new_ds.name, str(new_ds.id))
                    _combo.setCurrentIndex(_combo.count() - 2)
                else:
                    _combo.setCurrentIndex(0)

            src_combo.currentIndexChanged.connect(_on_src_combo_changed)
            form.addRow(t("Data Source"), src_combo)

            col_edit = QLineEdit()
            col_edit.setPlaceholderText("e.g. temperature")
            col_edit.setToolTip(t("Column whose value will be displayed or aggregated"))
            col_edit.setText(getattr(cur_binding, "column", "") if cur_binding else "")
            form.addRow(t("Column"), col_edit)

            match_field_edit = QLineEdit()
            match_field_edit.setPlaceholderText(t("(optional) e.g. zone_name"))
            match_field_edit.setText(getattr(cur_binding, "match_field", "") if cur_binding else "")
            match_field_edit.setToolTip(t("Optional source field used to match this element"))
            form.addRow(t("Filter Field"), match_field_edit)

            match_val_edit = QLineEdit()
            match_val_edit.setPlaceholderText("{{element.name}}")
            match_val_edit.setText(
                getattr(cur_binding, "match_value", "{{element.name}}") if cur_binding
                else "{{element.name}}"
            )
            match_val_edit.setToolTip(t("Value to match; supports {{element.name}} and {{element.id}}"))
            form.addRow(t("Filter Value"), match_val_edit)

            agg_combo = QComboBox()
            for agg in ("first", "last", "sum", "avg", "count"):
                agg_combo.addItem(agg)
            agg_combo.setCurrentText(getattr(cur_binding, "aggregate", "first") if cur_binding else "first")
            agg_combo.setToolTip(t("How multiple matching source values are combined"))
            form.addRow(t("Aggregate"), agg_combo)

            main_v.addLayout(form)
            main_v.addWidget(QLabel(
                "<small>" + t("Use {{element.name}} or {{element.id}} as dynamic filter values.") + "</small>"
            ))

            btn_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            btn_clear = QPushButton(t("Clear Binding"))
            btn_clear.setToolTip(t("Remove the data-source binding from this metadata key"))
            btn_box.addButton(btn_clear, QDialogButtonBox.ButtonRole.ResetRole)
            btn_box.accepted.connect(dlg.accept)
            btn_box.rejected.connect(dlg.reject)
            btn_clear.clicked.connect(lambda: (dlg.done(2)))
            main_v.addWidget(btn_box)

            result = dlg.exec()
            if result == 2:
                # Clear binding
                bindings.pop(key, None)
                self.metadata_binding_changed.emit(self._etype, str(element.id), key, None)
                # Update source cell
                src_item = table.item(row, 3)
                if src_item:
                    src_item.setText("—")
                    src_item.setForeground(table.palette().color(table.palette().ColorRole.PlaceholderText))
            elif result == 1:  # Accepted
                sid = src_combo.currentData()
                col = col_edit.text().strip()
                # Guard: sentinel value means no real source was selected
                if sid and col and sid != "__new__":
                    from bimap.models.zone import MetadataKeyBinding
                    b = MetadataKeyBinding(
                        source_id=sid,
                        column=col,
                        match_field=match_field_edit.text().strip(),
                        match_value=match_val_edit.text().strip() or "{{element.name}}",
                        aggregate=agg_combo.currentText(),
                    )
                    bindings[key] = b
                    self.metadata_binding_changed.emit(self._etype, str(element.id), key, b)
                    src_item = table.item(row, 3)
                    if src_item:
                        src_item.setText(_source_label(key))
                        src_item.setForeground(table.palette().color(table.palette().ColorRole.Highlight))

        table.cellDoubleClicked.connect(_on_cell_double_clicked)
        self._meta_layout.addWidget(table, 1)

        # ── Add row ──────────────────────────────────────────────────────── #
        btn_row = QHBoxLayout()
        key_combo = QComboBox()
        key_combo.setEditable(True)
        key_combo.setPlaceholderText(t("Key"))
        key_combo.setMinimumWidth(100)
        layer_name = getattr(element, "layer", "Default")
        if self._project:
            for lyr in getattr(self._project, "layers", []):
                if lyr.name == layer_name:
                    for k in lyr.key_library:
                        if key_combo.findText(k) < 0:
                            key_combo.addItem(k)
                    break
        val_edit = QLineEdit()
        val_edit.setPlaceholderText(t("Value"))
        btn_add = QPushButton(t("+ Add"))
        key_combo.setToolTip(t("Metadata attribute name"))
        val_edit.setToolTip(t("Metadata attribute value"))
        btn_add.setToolTip(t("Add this metadata attribute"))

        def _add_row() -> None:
            key = key_combo.currentText().strip()
            val = val_edit.text()
            if not key:
                return
            self.metadata_changed.emit(self._etype, str(element.id), key, val)
            metadata[key] = val
            _load()
            key_combo.clearEditText()
            val_edit.clear()

        btn_add.clicked.connect(_add_row)
        btn_row.addWidget(key_combo)
        btn_row.addWidget(val_edit)
        btn_row.addWidget(btn_add)
        self._meta_layout.addLayout(btn_row)

        btn_rm = QPushButton(t("Remove Selected"))
        btn_rm.setToolTip(t("Delete the selected metadata attributes"))

        def _remove_row() -> None:
            rows = {i.row() for i in table.selectedItems()}
            for r in sorted(rows, reverse=True):
                k_item = table.item(r, 0)
                if k_item:
                    key = k_item.text()
                    self.metadata_changed.emit(self._etype, str(element.id), key, None)
                    metadata.pop(key, None)
                    hidden[:] = [h for h in hidden if h != key]
                    bindings.pop(key, None)
                table.removeRow(r)

        btn_rm.clicked.connect(_remove_row)
        self._meta_layout.addWidget(btn_rm)

        # ── Extension controls (zone / keypoint only) ─────────────────────── #
        if hasattr(element, "extension_html"):
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color: #3C3C3C; margin-top: 4px;")
            self._meta_layout.addWidget(sep)

            html = getattr(element, "extension_html", "")
            etype = self._etype

            extension_name = getattr(element, "extension_name", "")
            if not extension_name and self._project:
                extension_html = getattr(element, "extension_html", "")
                matching_template = next(
                    (
                        template
                        for template in getattr(self._project, "extension_library", [])
                        if template.html == extension_html
                    ),
                    None,
                )
                extension_name = getattr(matching_template, "name", "")
            displayed_extension_name = (
                t("Custom Extension")
                if not extension_name or extension_name == "Custom Extension"
                else extension_name
            )
            extension_box = QGroupBox(t("Extension"))
            extension_layout = QVBoxLayout(extension_box)
            extension_layout.setContentsMargins(6, 8, 6, 6)
            extension_name_label = QLabel(displayed_extension_name)
            extension_name_label.setWordWrap(True)
            extension_name_label.setToolTip(t("Name of the extension assigned to this element"))
            extension_layout.addWidget(QLabel(t("Extension Name")))
            extension_layout.addWidget(extension_name_label)

            ext_row = QVBoxLayout()
            ext_row.setSpacing(4)
            btn_set_ext = QPushButton(
                t("Edit Extension\u2026") if html else t("Set Extension\u2026")
            )
            btn_set_ext.setToolTip(t("Choose an extension from the library or edit custom HTML"))
            btn_set_ext.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )

            def _open_extension_picker(_checked=False, _el=element, _et=etype) -> None:
                library = getattr(self._project, "extension_library", []) if self._project else []
                if library:
                    dlg = QDialog(self)
                    dlg.setWindowTitle(t("Set Extension"))
                    dlg.resize(380, 300)
                    lv = QVBoxLayout(dlg)
                    lv.addWidget(QLabel(t("Select from library or choose Custom:")))
                    lst = QListWidget()
                    lst.addItem(t("\u270f\u2002Custom (open editor)"))
                    for tpl in library:
                        lst.addItem(tpl.name)
                    lst.setCurrentRow(0)
                    lv.addWidget(lst)
                    btns = QDialogButtonBox(
                        QDialogButtonBox.StandardButton.Ok
                        | QDialogButtonBox.StandardButton.Cancel
                    )
                    btns.accepted.connect(dlg.accept)
                    btns.rejected.connect(dlg.reject)
                    lv.addWidget(btns)
                    if dlg.exec() and lst.currentRow() >= 0:
                        row = lst.currentRow()
                        if row == 0:
                            from bimap.ui.dialogs.extension_editor_dialog import ExtensionEditorDialog
                            editor = ExtensionEditorDialog(_el, _et, self)
                            if editor.exec():
                                self._emit("extension_html", editor.html_result)
                                self._emit("extension_name", "Custom Extension")
                                try:
                                    _el.extension_html = editor.html_result
                                    _el.extension_name = "Custom Extension"
                                except Exception:
                                    pass
                                self._setup_metadata_tab(_el.metadata, _el)
                        else:
                            tpl = library[row - 1]
                            self._emit("extension_html", tpl.html)
                            self._emit("extension_name", tpl.name)
                            try:
                                _el.extension_html = tpl.html
                                _el.extension_name = tpl.name
                            except Exception:
                                pass
                            self._setup_metadata_tab(_el.metadata, _el)
                else:
                    from bimap.ui.dialogs.extension_editor_dialog import ExtensionEditorDialog
                    editor = ExtensionEditorDialog(_el, _et, self)
                    if editor.exec():
                        self._emit("extension_html", editor.html_result)
                        self._emit("extension_name", "Custom Extension")
                        try:
                            _el.extension_html = editor.html_result
                            _el.extension_name = "Custom Extension"
                        except Exception:
                            pass
                        self._setup_metadata_tab(_el.metadata, _el)

            btn_set_ext.clicked.connect(_open_extension_picker)
            ext_row.addWidget(btn_set_ext)

            if html:
                btn_view = QPushButton(t("Open Data Viewer"))
                btn_view.setToolTip(t("Open the selected extension with the current element data"))
                btn_view.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )

                def _open_viewer(_checked=False, _el=element, _et=etype) -> None:
                    from bimap.ui.dialogs.extension_viewer_dialog import ExtensionViewerDialog
                    dlg = ExtensionViewerDialog(_el, _et, self)
                    dlg.show()

                btn_view.clicked.connect(_open_viewer)
                ext_row.addWidget(btn_view)

            ext_row.addStretch()
            extension_layout.addLayout(ext_row)
            self._meta_layout.addWidget(extension_box)

        # ── Fill Form controls (zone / keypoint) ───────────────────────── #
        if self._project and hasattr(self._project, "form_designs"):
            etype = self._etype
            applicable = [
                f for f in self._project.form_designs
                if f.target in ("both", etype)
            ]
            if applicable:
                sep2 = QFrame()
                sep2.setFrameShape(QFrame.Shape.HLine)
                sep2.setStyleSheet("color: #3C3C3C; margin-top: 4px;")
                self._meta_layout.addWidget(sep2)

                forms_row = QHBoxLayout()
                form_combo = QComboBox()
                for fd in applicable:
                    form_combo.addItem(fd.name, str(fd.id))
                forms_row.addWidget(form_combo, 1)

                btn_fill = QPushButton(t("Fill Form\u2026"))
                btn_fill.setToolTip(t("Open the selected form and write its answers to metadata"))

                def _fill_form(_checked=False, _el=element, _et=etype) -> None:
                    idx = form_combo.currentIndex()
                    if idx < 0:
                        return
                    chosen_id = form_combo.itemData(idx)
                    chosen = next(
                        (fd for fd in applicable if str(fd.id) == chosen_id), None
                    )
                    if chosen is None:
                        return
                    from bimap.ui.dialogs.form_fill_dialog import FormFillDialog

                    def _live_update(el: Any, key: str, val: str) -> None:
                        self.metadata_changed.emit(self._etype, str(el.id), key, val)
                        # Refresh the metadata table in real time while the dialog is open
                        self._setup_metadata_tab(el.metadata, el)

                    dlg = FormFillDialog(chosen, _el, _et, self, on_change=_live_update)
                    if dlg.exec():
                        # Re-render metadata tab to show filled values
                        self._setup_metadata_tab(_el.metadata, _el)
                        if self._project:
                            self._project.mark_modified()

                btn_fill.clicked.connect(_fill_form)
                forms_row.addWidget(btn_fill)
                self._meta_layout.addLayout(forms_row)

    def _populate_keypoint(self, kp: "Keypoint") -> None:
        self._title.setText(t("Keypoint"))

        title_edit = self._add_line_edit(t("Title"), kp.info_card.title)
        title_edit.setToolTip(t("Main title shown in the key point information card"))
        title_edit.editingFinished.connect(
            lambda: self._emit("info_card.title", title_edit.text())
        )
        sub_edit = self._add_line_edit(t("Subtitle"), kp.info_card.subtitle)
        sub_edit.setToolTip(t("Secondary text shown below the key point title"))
        sub_edit.editingFinished.connect(
            lambda: self._emit("info_card.subtitle", sub_edit.text())
        )
        notes = QTextEdit(kp.info_card.notes)
        notes.setMaximumHeight(80)
        notes.setToolTip(t("Additional information shown in the key point information card"))
        notes.textChanged.connect(lambda: self._emit("info_card.notes", notes.toPlainText()))
        self._form.addRow(t("Notes"), notes)
        url_edit = self._add_line_edit(t("URL"), kp.info_card.link_url)
        url_edit.setToolTip(t("Optional web link associated with this key point"))
        url_edit.editingFinished.connect(
            lambda: self._emit("info_card.link_url", url_edit.text())
        )

        color_btn = ColorButton(kp.icon_color)
        color_btn.setToolTip(t("Color used for the key point marker"))
        color_btn.color_changed.connect(lambda c: self._emit("icon_color", c))
        self._form.addRow(t("Pin Color"), color_btn)

        size_edit = QLineEdit(str(kp.icon_size))
        size_edit.setValidator(QIntValidator(8, 40, size_edit))
        size_edit.setToolTip(t("Marker size in pixels (8 to 40)"))
        size_edit.editingFinished.connect(
            lambda: self._emit("icon_size", int(size_edit.text() or "16"))
        )
        self._form.addRow(t("Pin Size"), size_edit)

        # ── Icon picker ─────────────────────────────────────────────────── #
        icon_row = QHBoxLayout()
        icon_combo = QComboBox()
        _builtin_icons = [("pin", t("Pin")), ("circle", t("Circle")),
                          ("square", t("Square")), ("diamond", t("Diamond")),
                          ("star", t("Star"))]
        for val, label in _builtin_icons:
            icon_combo.addItem(label, val)
        current_icon = getattr(kp, "icon", "pin")
        idx = next((i for i in range(icon_combo.count()) if icon_combo.itemData(i) == current_icon), -1)
        if idx >= 0:
            icon_combo.setCurrentIndex(idx)
        else:
            icon_combo.addItem(t("Custom…"), current_icon)
            icon_combo.setCurrentIndex(icon_combo.count() - 1)
        icon_combo.currentIndexChanged.connect(
            lambda _: self._emit("icon", icon_combo.currentData())
        )
        icon_combo.setToolTip(t("Choose the marker shape or a custom icon"))
        icon_row.addWidget(icon_combo, 1)

        btn_font_icons = QPushButton(t("Font icons…"))
        btn_font_icons.setToolTip(t("Choose from all available font icons"))

        def _choose_font_icon() -> None:
            from bimap.ui.dialogs.icon_font_dialog import IconFontDialog
            dlg = IconFontDialog(current_icon, self)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_value:
                self._emit("icon", dlg.selected_value)

        btn_font_icons.clicked.connect(_choose_font_icon)
        icon_row.addWidget(btn_font_icons)

        btn_icon_browse = QPushButton(t("Browse…"))
        btn_icon_browse.setToolTip(t("Choose an image file for a custom marker icon"))

        def _browse_icon() -> None:
            path, _ = QFileDialog.getOpenFileName(
                self, t("Choose Icon"), "",
                "Image files (*.svg *.png *.jpg *.jpeg *.bmp *.ico)"
            )
            if path:
                # Remove old custom entry if present
                for i in range(icon_combo.count()):
                    if (icon_combo.itemData(i) not in ("pin", "circle", "square", "diamond", "star")
                            and icon_combo.itemData(i) is not None):
                        icon_combo.removeItem(i)
                        break
                icon_combo.addItem(t("Custom…"), path)
                icon_combo.setCurrentIndex(icon_combo.count() - 1)
                self._emit("icon", path)

        btn_icon_browse.clicked.connect(_browse_icon)
        icon_row.addWidget(btn_icon_browse)
        self._form.addRow(t("Icon"), icon_row)

        lat_edit = QLineEdit(f"{kp.lat:.6f}")
        lat_edit.setValidator(QDoubleValidator(-90.0, 90.0, 6, lat_edit))
        lat_edit.setToolTip(t("Latitude in decimal degrees (-90 to 90)"))
        lat_edit.editingFinished.connect(
            lambda: self._emit("lat", float((lat_edit.text() or "0").replace(",", ".")))
        )
        self._form.addRow(t("Latitude"), lat_edit)

        lon_edit = QLineEdit(f"{kp.lon:.6f}")
        lon_edit.setValidator(QDoubleValidator(-180.0, 180.0, 6, lon_edit))
        lon_edit.setToolTip(t("Longitude in decimal degrees (-180 to 180)"))
        lon_edit.editingFinished.connect(
            lambda: self._emit("lon", float((lon_edit.text() or "0").replace(",", ".")))
        )
        self._form.addRow(t("Longitude"), lon_edit)

        # ── Linked Form Design ─────────────────────────────────────────────── #
        self._add_form_design_picker(kp, "keypoint")

        self._setup_metadata_tab(kp.metadata, kp)

    def _populate_annotation(self, ann: "Annotation") -> None:
        self._title.setText(t("Annotation"))
        content = QTextEdit(ann.content)
        content.setMinimumHeight(60)
        content.setToolTip(t("Text displayed inside the annotation"))
        content.textChanged.connect(lambda: self._emit("content", content.toPlainText()))
        self._form.addRow(t("Text"), content)

        fs_edit = QLineEdit(str(ann.style.font_size))
        fs_edit.setValidator(QIntValidator(6, 72, fs_edit))
        fs_edit.setToolTip(t("Annotation font size in points (6 to 72)"))
        fs_edit.editingFinished.connect(
            lambda: self._emit("style.font_size", int(fs_edit.text() or "12"))
        )
        self._form.addRow(t("Font Size"), fs_edit)

        color_btn = ColorButton(ann.style.color)
        color_btn.setToolTip(t("Color used for annotation text"))
        color_btn.color_changed.connect(lambda c: self._emit("style.color", c))
        self._form.addRow(t("Text Color"), color_btn)

        bg_btn = ColorButton(ann.style.background_color)
        bg_btn.setToolTip(t("Background color of the annotation box"))
        bg_btn.color_changed.connect(lambda c: self._emit("style.background_color", c))
        self._form.addRow(t("Background"), bg_btn)

        if hasattr(ann, "metadata"):
            self._setup_metadata_tab(ann.metadata, ann)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _add_form_design_picker(self, element: Any, etype: str) -> None:
        """Add a Form Design combo selector and Fill button to the Style tab."""
        # Collect ALL forms available in the project (not filtered by etype)
        all_forms: list = []
        if self._project and hasattr(self._project, "form_designs"):
            all_forms = list(self._project.form_designs)

        # If no forms exist, skip this section entirely — user opens Form Designer via Data menu
        if not all_forms:
            return

        form_grp = QGroupBox(t("Form"))
        form_layout = QFormLayout(form_grp)

        form_combo = QComboBox()
        form_combo.setToolTip(t("Select a form design to populate metadata fields"))
        form_combo.addItem(t("--- none ---"), "")
        for fd in all_forms:
            form_combo.addItem(fd.name, str(fd.id))
        current_fid = getattr(element, "form_design_id", "")
        cur_idx = form_combo.findData(current_fid)
        form_combo.setCurrentIndex(max(0, cur_idx))

        def _on_form_selected(idx: int, _el=element, _et=etype) -> None:
            fid = form_combo.itemData(idx) or ""
            self._emit("form_design_id", fid)
            if fid:
                chosen = next((fd for fd in all_forms if str(fd.id) == fid), None)
                if chosen:
                    meta = getattr(_el, "metadata", None)
                    if meta is not None:
                        for field in chosen.fields:
                            if field.label not in meta:
                                meta[field.label] = field.default_value
                        self._setup_metadata_tab(meta, _el)
                    if self._project:
                        self._project.mark_modified()

        form_combo.currentIndexChanged.connect(_on_form_selected)
        form_layout.addRow(t("Design"), form_combo)

        # Fill Form button (opens form-fill dialog)
        btn_fill = QPushButton(t("Fill Form..."))
        btn_fill.setToolTip(t("Open the selected form and write its answers to metadata"))

        def _fill(_checked=False, _el=element, _et=etype) -> None:
            idx = form_combo.currentIndex()
            fid = form_combo.itemData(idx) if idx >= 0 else ""
            if not fid:
                return
            chosen = next((fd for fd in all_forms if str(fd.id) == fid), None)
            if not chosen:
                return
            from bimap.ui.dialogs.form_fill_dialog import FormFillDialog

            def _live_update(el: Any, key: str, val: str) -> None:
                self.metadata_changed.emit(self._etype, str(el.id), key, val)
                self._setup_metadata_tab(el.metadata, el)

            dlg = FormFillDialog(chosen, _el, _et, self, on_change=_live_update)
            if dlg.exec():
                self._setup_metadata_tab(_el.metadata, _el)
                if self._project:
                    self._project.mark_modified()

        btn_fill.clicked.connect(_fill)
        form_layout.addRow(btn_fill)
        self._form.addRow(form_grp)

    def _add_line_edit(self, label: str, value: str) -> QLineEdit:
        edit = QLineEdit(value)
        self._form.addRow(label, edit)
        return edit

    def _emit(self, field: str, value: Any) -> None:
        if self._element:
            self.element_changed.emit(self._etype, str(self._element.id), field, value)

    # ── Data Feature Display ───────────────────────────────────────────────────

    def _populate_data_feature(self, data: dict[str, Any]) -> None:
        """Display attributes of a selected WFS/CSV/REST API data feature."""
        source_name = data.get("_source_name", "Data Feature")
        feature_type = data.get("_geom_type", "Unknown")
        self._title.setText(f"{source_name} — {feature_type}")

        # Show layer info
        info_grp = QGroupBox(t("Feature Info"))
        info_layout = QFormLayout(info_grp)

        # Source info
        src_label = QLabel(source_name)
        src_label.setStyleSheet("font-weight: normal;")
        info_layout.addRow(t("Source:"), src_label)

        # Geometry type
        geom_label = QLabel(feature_type or "—")
        geom_label.setStyleSheet("font-weight: normal;")
        info_layout.addRow(t("Type:"), geom_label)

        # Coordinates (if available)
        lat_s = data.get("_lat")
        lon_s = data.get("_lon")
        if lat_s and lon_s:
            coord_label = QLabel(f"{lat_s}, {lon_s}")
            coord_label.setStyleSheet("font-weight: normal;")
            coord_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            info_layout.addRow(t("Coordinates:"), coord_label)

        self._form.addRow(info_grp)

        # Show all attributes in a table
        attrs_grp = QGroupBox(t("Attributes"))
        attrs_layout = QVBoxLayout(attrs_grp)
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels([t("Field"), t("Value")])
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setToolTip(t("Read-only attributes received from the selected data source"))

        # Filter out internal fields (starting with _) and show user attributes
        user_attrs = {k: v for k, v in data.items() if not k.startswith("_")}
        table.setRowCount(len(user_attrs))

        for row_idx, (key, value) in enumerate(user_attrs.items()):
            key_item = QTableWidgetItem(str(key))
            val_item = QTableWidgetItem(str(value))
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            val_item.setFlags(val_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_idx, 0, key_item)
            table.setItem(row_idx, 1, val_item)

        table.resizeColumnsToContents()
        attrs_layout.addWidget(table)
        self._form.addRow(attrs_grp)

