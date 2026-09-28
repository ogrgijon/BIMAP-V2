"""Unified Map Composer dialog — handles both PDF export and print preview."""

from __future__ import annotations

import copy

from PyQt6.QtCore import QEvent, QPointF, Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bimap.config import MAX_ZOOM, MIN_ZOOM, PDF_PAGE_SIZES
from bimap.i18n import t
from bimap.models.pdf_layout import PageOrientation, PDFLayout
from bimap.ui._utils import add_top_right_help_button, show_help_dialog


class MapComposerDialog(QDialog):
    """
    Full-featured map composer:
     • Page & Zoom settings
     • Legend editor (per-layer visibility + custom labels)
     • Info Box editor (free-text + author/date)
     • Output file picker with both Export PDF and Print buttons
    """

    def __init__(
        self,
        layout: PDFLayout,
        current_zoom: int,
        layer_names: list[str],
        parent: QWidget | None = None,
        mode: str = "export",          # kept for backward-compat: ignored
        canvas_widget: QWidget | None = None,
        project_layers: list | None = None,
        project_name: str = "",
    ) -> None:
        super().__init__(parent)
        self._layout = layout
        self._current_zoom = current_zoom
        self._layer_names = layer_names
        self._canvas_widget = canvas_widget
        self._project_layers: list = project_layers or []
        self._project_name: str = project_name
        self._output_path: str = ""
        self._accepted_as: str = ""

        # Debounce timer so preview updates 350 ms after the last change
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(350)
        self._preview_timer.timeout.connect(self._refresh_preview)

        # Preview panning state
        self._preview_drag_start: QPointF | None = None
        self._preview_frame_w: int = 400
        self._preview_frame_h: int = 480

        self.setWindowTitle(t("Map Composer"))
        self.setMinimumSize(960, 600)
        self._setup_ui()

    # ── UI construction ────────────────────────────────────────────────────── #

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(12, 12, 12, 12)
        add_top_right_help_button(self, self._show_help)

        content = QWidget()
        root_layout = QHBoxLayout(content)
        root_layout.setSpacing(12)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # ── Left pane: settings ──────────────────────────────────────────── #
        left = QWidget()
        left.setMinimumWidth(440)
        left.setMaximumWidth(480)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(10)

        tabs = QTabWidget()
        tabs.addTab(self._make_page_tab(), t("Page && Zoom"))
        tabs.addTab(self._make_legend_tab(), t("Legend"))
        tabs.addTab(self._make_title_block_tab(), t("Title Block"))
        tabs.addTab(self._make_info_box_tab(), t("Info Box"))
        lv.addWidget(tabs)

        lv.addWidget(self._make_output_section())

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton(t("Cancel"))
        self._btn_print = QPushButton(t("🖶  Print…"))
        self._btn_export = QPushButton(t("📄  Export PDF"))
        self._btn_export.setDefault(True)
        btn_cancel.clicked.connect(self.reject)
        self._btn_print.clicked.connect(self._on_print)
        self._btn_export.clicked.connect(self._on_export)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self._btn_print)
        btn_row.addWidget(self._btn_export)
        lv.addLayout(btn_row)

        root_layout.addWidget(left)

        # ── Right pane: live preview ─────────────────────────────────────── #
        root_layout.addWidget(self._make_preview_pane(), 1)
        root.addWidget(content, 1)

        self._connect_preview_signals()
        QTimer.singleShot(0, self._refresh_preview)

    def _show_help(self) -> None:
        show_help_dialog(self, t("Application Help"), t("Map Composer window help"))

    def _make_page_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setContentsMargins(12, 14, 12, 12)
        form.setVerticalSpacing(10)

        self._size_combo = QComboBox()
        for key in PDF_PAGE_SIZES:
            self._size_combo.addItem(key)
        self._size_combo.setCurrentText(self._layout.page_size)
        form.addRow(t("Page Size"), self._size_combo)

        self._orient_combo = QComboBox()
        self._orient_combo.addItem(t("landscape"), "landscape")
        self._orient_combo.addItem(t("portrait"), "portrait")
        idx = self._orient_combo.findData(str(self._layout.orientation))
        self._orient_combo.setCurrentIndex(max(0, idx))
        form.addRow(t("Orientation"), self._orient_combo)

        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 600)
        self._dpi_spin.setSingleStep(50)
        self._dpi_spin.setValue(self._layout.dpi)
        form.addRow(t("DPI"), self._dpi_spin)

        form.addRow(QLabel())  # spacer

        zoom_w = QWidget()
        zoom_row = QHBoxLayout(zoom_w)
        zoom_row.setContentsMargins(0, 0, 0, 0)
        self._zoom_spin = QSpinBox()
        self._zoom_spin.setRange(MIN_ZOOM, MAX_ZOOM)
        current = (
            self._layout.capture_zoom
            if self._layout.capture_zoom is not None
            else self._current_zoom
        )
        self._zoom_spin.setValue(current)
        note = QLabel(f"  (export quality only — current: {self._current_zoom})")
        note.setStyleSheet("font-size:10px; color:#888888;")
        zoom_row.addWidget(self._zoom_spin)
        zoom_row.addWidget(note)
        zoom_row.addStretch()
        form.addRow(t("Capture Zoom"), zoom_w)

        return tab

    def _make_legend_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(12, 14, 12, 12)
        vbox.setSpacing(8)

        self._legend_chk = QCheckBox(t("Show legend overlay on output"))
        self._legend_chk.setChecked(self._layout.show_legend)
        vbox.addWidget(self._legend_chk)

        title_row = QFormLayout()
        title_row.setContentsMargins(0, 4, 0, 4)
        self._legend_title_edit = QLineEdit(self._layout.legend_title)
        title_row.addRow(t("Legend Title"), self._legend_title_edit)
        vbox.addLayout(title_row)

        vbox.addWidget(
            QLabel(t("Zones (uncheck to hide, edit Display Label to rename):"))
        )

        self._legend_table = QTableWidget(len(self._layer_names), 2)
        self._legend_table.setHorizontalHeaderLabels([t("Layer"), t("Display Label")])
        self._legend_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._legend_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._legend_table.verticalHeader().setVisible(False)
        self._legend_table.setMaximumHeight(180)
        self._legend_table.setAlternatingRowColors(True)

        for i, name in enumerate(self._layer_names):
            chk_item = QTableWidgetItem(name)
            chk_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            chk_item.setCheckState(
                Qt.CheckState.Unchecked
                if name in self._layout.legend_hidden_layers
                else Qt.CheckState.Checked
            )
            lbl_item = QTableWidgetItem(
                self._layout.legend_custom_labels.get(name, name)
            )
            self._legend_table.setItem(i, 0, chk_item)
            self._legend_table.setItem(i, 1, lbl_item)

        vbox.addWidget(self._legend_table)

        def _toggle_legend(checked: bool) -> None:
            self._legend_title_edit.setEnabled(checked)
            self._legend_table.setEnabled(checked)

        self._legend_chk.toggled.connect(_toggle_legend)
        _toggle_legend(self._layout.show_legend)

        vbox.addStretch()
        return tab

    def _make_title_block_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(12, 14, 12, 12)
        vbox.setSpacing(8)

        self._tb_enabled_chk = QCheckBox(t("Show architectural title block on output"))
        self._tb_enabled_chk.setChecked(self._layout.tb_enabled)
        vbox.addWidget(self._tb_enabled_chk)

        note = QLabel(
            "Height auto-adjusts: ~7.5 % of printable width "
            "(≈20 mm A4-landscape, ≈28 mm A3-landscape, 50 pt min for portrait)."
        )
        note.setWordWrap(True)
        note.setStyleSheet("font-size:10px; color:#888888;")
        vbox.addWidget(note)

        # All fields live inside a container widget so a single
        # setEnabled(False) greys them all out when the checkbox is off.
        self._tb_fields_widget = QWidget()
        form = QFormLayout(self._tb_fields_widget)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setContentsMargins(0, 6, 0, 0)
        form.setVerticalSpacing(8)

        self._tb_project_name_edit = QLineEdit(self._layout.tb_project_name)
        self._tb_project_name_edit.setPlaceholderText(
            self._project_name or t("Project Name")
        )
        form.addRow(t("Project Name"), self._tb_project_name_edit)

        self._tb_desc_edit = QLineEdit(self._layout.tb_description)
        self._tb_desc_edit.setPlaceholderText(t("Description"))
        form.addRow(t("Description"), self._tb_desc_edit)

        self._tb_drawn_edit = QLineEdit(self._layout.tb_drawn_by)
        self._tb_drawn_edit.setPlaceholderText(t("Drawn by"))
        form.addRow(t("Drawn by"), self._tb_drawn_edit)

        self._tb_checked_edit = QLineEdit(self._layout.tb_checked_by)
        self._tb_checked_edit.setPlaceholderText(t("Checked by"))
        form.addRow(t("Checked by"), self._tb_checked_edit)

        self._tb_rev_edit = QLineEdit(self._layout.tb_revision)
        self._tb_rev_edit.setPlaceholderText(t("Revision"))
        form.addRow(t("Revision"), self._tb_rev_edit)

        self._tb_scale_edit = QLineEdit(self._layout.tb_scale)
        self._tb_scale_edit.setPlaceholderText(t("Scale"))
        form.addRow(t("Scale"), self._tb_scale_edit)

        self._tb_sheet_edit = QLineEdit(self._layout.tb_sheet)
        self._tb_sheet_edit.setPlaceholderText(t("Sheet"))
        form.addRow(t("Sheet"), self._tb_sheet_edit)

        vbox.addWidget(self._tb_fields_widget)
        vbox.addStretch()

        def _toggle_tb(checked: bool) -> None:
            self._tb_fields_widget.setEnabled(checked)

        self._tb_enabled_chk.toggled.connect(_toggle_tb)
        _toggle_tb(self._layout.tb_enabled)

        return tab

    def _make_info_box_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(12, 14, 12, 12)
        vbox.setSpacing(8)

        self._info_chk = QCheckBox(t("Show info box overlay on output"))
        self._info_chk.setChecked(self._layout.show_info_box)
        vbox.addWidget(self._info_chk)

        vbox.addWidget(QLabel(t("Text block (appears in the info box):")))
        self._info_text_edit = QTextEdit(self._layout.info_box_text)
        self._info_text_edit.setMaximumHeight(110)
        self._info_text_edit.setPlaceholderText(
            "Enter free-form text to appear in the info box overlay…"
        )
        vbox.addWidget(self._info_text_edit)

        form_row = QFormLayout()
        form_row.setContentsMargins(0, 6, 0, 4)
        form_row.setVerticalSpacing(6)
        self._info_author_edit = QLineEdit(self._layout.info_box_author)
        self._info_author_edit.setPlaceholderText(t("Author"))
        form_row.addRow(t("Author"), self._info_author_edit)
        self._info_date_edit = QLineEdit(self._layout.info_box_date)
        self._info_date_edit.setPlaceholderText(t("Date"))
        form_row.addRow(t("Date"), self._info_date_edit)
        vbox.addLayout(form_row)

        def _toggle_info(checked: bool) -> None:
            for w in (
                self._info_text_edit,
                self._info_author_edit,
                self._info_date_edit,
            ):
                w.setEnabled(checked)

        self._info_chk.toggled.connect(_toggle_info)
        _toggle_info(self._layout.show_info_box)

        vbox.addStretch()
        return tab

    def _make_output_section(self) -> QGroupBox:
        grp = QGroupBox(t("Output File  (required for Export PDF)"))
        row = QHBoxLayout(grp)
        row.setContentsMargins(8, 6, 8, 6)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(t("Choose output .pdf path…"))
        btn_browse = QPushButton(t("Browse…"))
        btn_browse.clicked.connect(self._browse)
        row.addWidget(self._path_edit)
        row.addWidget(btn_browse)
        return grp

    # ── Preview pane ──────────────────────────────────────────────────────── #

    def _make_preview_pane(self) -> QWidget:
        pane = QWidget()
        vbox = QVBoxLayout(pane)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        hdr = QHBoxLayout()
        lbl = QLabel("Preview")
        lbl.setStyleSheet("font-weight: bold;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        scroll_hint = QLabel("🖱 scroll=zoom  drag=pan")
        scroll_hint.setStyleSheet("font-size:10px; color:#888888;")
        hdr.addWidget(scroll_hint)
        vbox.addLayout(hdr)

        self._preview_label = QLabel("Rendering…")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(400, 480)
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._preview_label.setStyleSheet(
            "background: #1E1E1E; border: 1px solid #3C3C3C; color: #555555;"
        )
        self._preview_label.setMouseTracking(True)
        self._preview_label.installEventFilter(self)
        vbox.addWidget(self._preview_label, 1)
        return pane

    def _connect_preview_signals(self) -> None:
        """Connect all form-change signals to the debounce timer."""
        _t = lambda *_: self._preview_timer.start()
        self._size_combo.currentIndexChanged.connect(_t)
        self._orient_combo.currentIndexChanged.connect(_t)
        self._dpi_spin.valueChanged.connect(_t)
        self._zoom_spin.valueChanged.connect(_t)
        self._legend_chk.toggled.connect(_t)
        self._legend_title_edit.textChanged.connect(_t)
        self._legend_table.itemChanged.connect(_t)
        self._tb_enabled_chk.toggled.connect(_t)
        self._tb_project_name_edit.textChanged.connect(_t)
        self._tb_desc_edit.textChanged.connect(_t)
        self._tb_drawn_edit.textChanged.connect(_t)
        self._tb_checked_edit.textChanged.connect(_t)
        self._tb_rev_edit.textChanged.connect(_t)
        self._tb_scale_edit.textChanged.connect(_t)
        self._tb_sheet_edit.textChanged.connect(_t)
        self._info_chk.toggled.connect(_t)
        self._info_text_edit.textChanged.connect(_t)
        self._info_author_edit.textChanged.connect(_t)
        self._info_date_edit.textChanged.connect(_t)

    def _refresh_preview(self) -> None:
        """Grab the canvas, apply page shape + zoom simulation, paint overlays."""
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QColor, QPainter, QPixmap

        if self._canvas_widget is None:
            self._preview_label.setText("No canvas available")
            return

        canvas_pm: QPixmap = self._canvas_widget.grab()
        if canvas_pm.isNull():
            self._preview_label.setText("Canvas unavailable")
            return

        tmp = self._temp_layout()

        # 1. Page aspect ratio from selected size + orientation
        # capture_zoom only controls tile resolution at export time — it does NOT
        # change the visible geographic extent, so no zoom manipulation of the grab.
        pw_pts, ph_pts = PDF_PAGE_SIZES.get(tmp.page_size, (595.27, 841.89))
        if tmp.orientation == PageOrientation.LANDSCAPE:
            pw_pts, ph_pts = ph_pts, pw_pts
        page_aspect = pw_pts / ph_pts  # width / height

        # 2. Fit page frame into the available label area
        avail_w = max(self._preview_label.width() - 24, 280)
        avail_h = max(self._preview_label.height() - 24, 360)
        if avail_w / avail_h > page_aspect:
            frame_h = avail_h
            frame_w = int(avail_h * page_aspect)
        else:
            frame_w = avail_w
            frame_h = int(avail_w / page_aspect)

        self._preview_frame_w = frame_w
        self._preview_frame_h = frame_h

        # 3. Scale canvas grab to fill the page frame (centre-crop to exact size)
        page_pm = canvas_pm.scaled(
            frame_w, frame_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if page_pm.width() != frame_w or page_pm.height() != frame_h:
            xo = (page_pm.width() - frame_w) // 2
            yo = (page_pm.height() - frame_h) // 2
            page_pm = page_pm.copy(xo, yo, frame_w, frame_h)

        # 4. Paint title block strip + info box overlays onto the page frame
        painter = QPainter(page_pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = page_pm.rect()
        self._paint_title_block(painter, r, tmp)
        if tmp.show_info_box:
            self._paint_info_box(painter, r, tmp)

        # 5. Zoom badge — shows the capture zoom that will be used at export
        self._paint_zoom_badge(painter, r, tmp)
        painter.end()

        # 6. Composite page frame (with drop-shadow) onto the dark label background
        lbl_w = max(self._preview_label.width() - 4, 400)
        lbl_h = max(self._preview_label.height() - 4, 480)
        final = QPixmap(lbl_w, lbl_h)
        final.fill(QColor("#1E1E1E"))
        fx = (lbl_w - frame_w) // 2
        fy = (lbl_h - frame_h) // 2
        p2 = QPainter(final)
        p2.setOpacity(0.35)
        p2.fillRect(QRect(fx + 4, fy + 4, frame_w, frame_h), QColor("#000000"))
        p2.setOpacity(1.0)
        p2.drawPixmap(fx, fy, page_pm)
        p2.setPen(QColor("#555555"))
        p2.drawRect(QRect(fx, fy, frame_w - 1, frame_h - 1))
        p2.end()

        self._preview_label.setPixmap(final)

    def _temp_layout(self) -> PDFLayout:
        """Return a PDFLayout copy reflecting the current form state (not committed to self._layout)."""
        tmp = copy.deepcopy(self._layout)
        tmp.page_size = self._size_combo.currentText()
        tmp.orientation = PageOrientation(self._orient_combo.currentData())
        tmp.dpi = self._dpi_spin.value()
        tmp.capture_zoom = self._zoom_spin.value()
        tmp.show_legend = self._legend_chk.isChecked()
        tmp.legend_title = self._legend_title_edit.text().strip()
        hidden: list[str] = []
        labels: dict[str, str] = {}
        for i in range(self._legend_table.rowCount()):
            chk = self._legend_table.item(i, 0)
            lbl = self._legend_table.item(i, 1)
            if chk:
                name = chk.text()
                if chk.checkState() == Qt.CheckState.Unchecked:
                    hidden.append(name)
                if lbl and lbl.text() != name:
                    labels[name] = lbl.text()
        tmp.legend_hidden_layers = hidden
        tmp.legend_custom_labels = labels
        tmp.tb_enabled = self._tb_enabled_chk.isChecked()
        tmp.tb_project_name = self._tb_project_name_edit.text().strip()
        tmp.tb_description = self._tb_desc_edit.text().strip()
        tmp.tb_drawn_by = self._tb_drawn_edit.text().strip()
        tmp.tb_checked_by = self._tb_checked_edit.text().strip()
        tmp.tb_revision = self._tb_rev_edit.text().strip()
        tmp.tb_scale = self._tb_scale_edit.text().strip()
        tmp.tb_sheet = self._tb_sheet_edit.text().strip()
        tmp.show_info_box = self._info_chk.isChecked()
        tmp.info_box_text = self._info_text_edit.toPlainText().strip()
        tmp.info_box_author = self._info_author_edit.text().strip()
        tmp.info_box_date = self._info_date_edit.text().strip()
        return tmp

    def _paint_zoom_badge(self, painter, rect, tmp: PDFLayout) -> None:
        """Draw a small 'zoom Z' badge at top-left so the user sees the capture zoom."""
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QColor, QFont
        z = tmp.capture_zoom if tmp.capture_zoom is not None else self._current_zoom
        text = f"zoom {z}"
        padding = 5
        font = QFont("Segoe UI", 8)
        painter.save()
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        bw = tw + padding * 2
        bh = fm.height() + padding * 2
        painter.setOpacity(0.80)
        painter.fillRect(QRect(rect.left() + 6, rect.top() + 6, bw, bh), QColor("#007ACC"))
        painter.setOpacity(1.0)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(
            QRect(rect.left() + 6 + padding, rect.top() + 6 + padding, tw, fm.height()),
            0, text,
        )
        painter.restore()

    def _paint_title_block(self, painter, rect, tmp: PDFLayout) -> None:
        """Draw the architectural title block strip at the bottom of the preview frame."""
        if not tmp.tb_enabled:
            # Title block off — show standalone floating legend instead if requested
            if tmp.show_legend and self._project_layers:
                self._paint_floating_legend(painter, rect, tmp)
            return
        from PyQt6.QtCore import QRect, QRectF, Qt
        from PyQt6.QtGui import QBrush, QColor, QFont, QPen

        # Scale height the same way as the renderer:
        # 7.5 % of strip width in pixels, clamped to [30 px, 20 % of frame height].
        strip_w_px = rect.width() - 2
        tb_h = max(30, min(int(rect.height() * 0.20), int(strip_w_px * 0.090)))
        y0 = rect.bottom() - tb_h
        x0 = rect.left() + 1
        strip_w = rect.width() - 2
        p = 4  # padding px

        col_title  = int(strip_w * 0.32)
        col_legend = int(strip_w * 0.36)
        col_meta   = strip_w - col_title - col_legend
        x_title  = x0
        x_meta   = x0 + col_title
        x_legend = x0 + col_title + col_meta
        row2_h   = int(tb_h * 0.38)
        row1_h   = tb_h - row2_h

        # Background
        painter.save()
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawRect(QRect(x0, y0, strip_w, tb_h))

        # Outer border
        painter.setPen(QPen(QColor("#111111"), 2))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawRect(QRect(x0, y0, strip_w - 1, tb_h - 1))

        # Dividers
        painter.setPen(QPen(QColor("#444444"), 1))
        painter.drawLine(x_meta, y0, x_meta, y0 + tb_h)
        painter.drawLine(x_legend, y0, x_legend, y0 + tb_h)
        painter.drawLine(x_title, y0 + row1_h, x_title + col_title, y0 + row1_h)
        painter.drawLine(x_meta,  y0 + row1_h, x_meta  + col_meta,  y0 + row1_h)
        painter.restore()

        # Accent band (title col left edge)
        acc_w = max(5, int(strip_w * 0.008))
        painter.save()
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(QBrush(QColor("#1E3A5F")))
        painter.drawRect(QRect(x_title, y0, acc_w, tb_h))
        painter.restore()

        # Project name (top-left)
        painter.save()
        f = QFont("Arial", max(7, int(tb_h * 0.20)))
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor("#111111"))
        painter.drawText(
            QRectF(x_title + acc_w + p, y0 + p, col_title - acc_w - p * 2, row1_h - p * 2),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            tmp.tb_project_name or self._project_name or "Project Name",
        )
        painter.restore()

        # Scale / sheet (bottom-left)
        painter.save()
        f2 = QFont("Arial", max(5, int(tb_h * 0.11)))
        painter.setFont(f2)
        painter.setPen(QColor("#555555"))
        painter.drawText(
            QRectF(x_title + acc_w + p, y0 + row1_h + p,
                   col_title - acc_w - p * 2, row2_h - p * 2),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"Scale: {tmp.tb_scale}    Sheet: {tmp.tb_sheet}",
        )
        painter.restore()

        # Description (top-middle)
        import datetime
        painter.save()
        f3 = QFont("Arial", max(5, int(tb_h * 0.13)))
        painter.setFont(f3)
        painter.setPen(QColor("#333333"))
        painter.drawText(
            QRectF(x_meta + p, y0 + p, col_meta - p * 2, row1_h - p * 2),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            tmp.tb_description,
        )
        painter.restore()

        # Meta cells (bottom-middle)
        meta_cells = [
            ("Drawn",   tmp.tb_drawn_by),
            ("Checked", tmp.tb_checked_by),
            ("Date",    tmp.info_box_date or datetime.date.today().isoformat()),
            ("Rev",     tmp.tb_revision),
        ]
        cw4 = col_meta // 4
        for ci, (cap, val) in enumerate(meta_cells):
            cx = x_meta + ci * cw4
            painter.save()
            f4c = QFont("Arial", max(4, int(tb_h * 0.09)))
            painter.setFont(f4c)
            painter.setPen(QColor("#888888"))
            painter.drawText(
                QRectF(cx + p, y0 + row1_h + 1, cw4 - p, int(row2_h * 0.4)),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                cap.upper(),
            )
            f4v = QFont("Arial", max(5, int(tb_h * 0.12)))
            painter.setFont(f4v)
            painter.setPen(QColor("#111111"))
            painter.drawText(
                QRectF(cx + p, y0 + row1_h + int(row2_h * 0.42), cw4 - p, int(row2_h * 0.55)),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                val,
            )
            painter.restore()

        # Legend column (right) — header band
        if tmp.show_legend and self._project_layers:
            layers = [
                lyr for lyr in self._project_layers
                if lyr.visible and lyr.name not in tmp.legend_hidden_layers
            ]
            hdr_h = max(10, int(tb_h * 0.24))
            painter.save()
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.setBrush(QBrush(QColor("#1E3A5F")))
            painter.drawRect(QRect(x_legend, y0, col_legend, hdr_h))
            painter.restore()

            painter.save()
            fhdr = QFont("Arial", max(5, int(hdr_h * 0.50)))
            fhdr.setBold(True)
            painter.setFont(fhdr)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(
                QRectF(x_legend + p, y0 + 1, col_legend - p * 2, hdr_h - 2),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                (tmp.legend_title or "LEGEND").upper(),
            )
            painter.restore()

            swatch_s = max(5, int(tb_h * 0.11))
            row_gap  = max(1, int(tb_h * 0.03))
            entry_h  = swatch_s + row_gap
            avail_h  = tb_h - hdr_h - p * 2
            max_rows = max(1, avail_h // entry_h)
            half     = (len(layers) + 1) // 2
            col2_w   = col_legend // 2

            flbl = QFont("Arial", max(4, int(swatch_s * 0.80)))
            painter.save()
            painter.setFont(flbl)
            for idx, lyr in enumerate(layers):
                col_idx = (idx // half) if len(layers) > max_rows else 0
                row_idx = (idx % half)  if len(layers) > max_rows else idx
                ex = x_legend + p + col_idx * col2_w
                ey = y0 + hdr_h + p + row_idx * entry_h
                if ey + swatch_s > y0 + tb_h - 1:
                    break
                fill = QColor(lyr.style.fill_color)
                fill.setAlpha(lyr.style.fill_alpha)
                painter.setPen(QPen(QColor(lyr.style.border_color), 1))
                painter.setBrush(QBrush(fill))
                painter.drawRect(QRect(ex, ey, swatch_s, swatch_s))
                label = tmp.legend_custom_labels.get(lyr.name, lyr.name)
                painter.setPen(QColor("#222222"))
                painter.drawText(
                    QRectF(ex + swatch_s + 2, ey, col2_w - swatch_s - p, swatch_s),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    label,
                )
            painter.restore()

    def _paint_floating_legend(self, painter, rect, tmp: PDFLayout) -> None:
        """Compact floating legend box — shown when title block is disabled."""
        from PyQt6.QtCore import QRect, QRectF, Qt
        from PyQt6.QtGui import QBrush, QColor, QFont, QPen

        layers = [
            lyr for lyr in self._project_layers
            if lyr.visible and lyr.name not in tmp.legend_hidden_layers
        ]
        if not layers:
            return

        p        = 6
        swatch_s = 10
        entry_h  = swatch_s + 3
        title_h  = 15
        box_h    = title_h + p + entry_h * len(layers) + p
        box_w    = 140
        x = rect.right() - box_w - p
        y = rect.top()   + p

        painter.save()
        painter.setPen(QPen(QColor("#888888"), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.drawRect(QRect(x, y, box_w, box_h))

        fhdr = QFont("Arial", 7)
        fhdr.setBold(True)
        painter.setFont(fhdr)
        painter.setPen(QColor("#111111"))
        painter.drawText(
            QRectF(x + p, y + 2, box_w - p * 2, title_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            (tmp.legend_title or "Legend").upper(),
        )

        flbl = QFont("Arial", 6)
        painter.setFont(flbl)
        for i, lyr in enumerate(layers):
            ey = y + title_h + p + i * entry_h
            fill = QColor(lyr.style.fill_color)
            fill.setAlpha(lyr.style.fill_alpha)
            painter.setPen(QPen(QColor(lyr.style.border_color), 1))
            painter.setBrush(QBrush(fill))
            painter.drawRect(QRect(x + p, ey, swatch_s, swatch_s))
            label = tmp.legend_custom_labels.get(lyr.name, lyr.name)
            painter.setPen(QColor("#222222"))
            painter.drawText(
                QRectF(x + p + swatch_s + 3, ey, box_w - p * 2 - swatch_s - 3, swatch_s),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
        painter.restore()

    def _paint_info_box(self, painter, rect, tmp: PDFLayout) -> None:
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QColor, QFont
        padding = 8
        font = QFont("Segoe UI", 8)
        painter.save()
        painter.setFont(font)
        fm = painter.fontMetrics()
        row_h = fm.height() + 2
        # Show text block AND structured fields simultaneously
        lines: list[str] = []
        if tmp.info_box_text:
            lines.extend(tmp.info_box_text.splitlines())
        if tmp.info_box_author:
            lines.append(f"Author: {tmp.info_box_author}")
        if tmp.info_box_date:
            lines.append(f"Date: {tmp.info_box_date}")
        if not lines:
            lines = ["(info box — no text set)"]
        box_h = row_h * len(lines) + padding * 2
        box_w = 200
        x = rect.left() + padding
        # Keep info box above the title block strip when it is visible
        strip_w_px = rect.width() - 2
        tb_px = max(30, min(int(rect.height() * 0.20), int(strip_w_px * 0.090))) if tmp.tb_enabled else 0
        y = rect.bottom() - tb_px - box_h - padding
        painter.setOpacity(0.88)
        painter.fillRect(QRect(x, y, box_w, box_h), QColor("#252526"))
        painter.setOpacity(1.0)
        painter.setPen(QColor("#D4D4D4"))
        for i, line in enumerate(lines):
            painter.drawText(
                QRect(x + padding, y + padding + row_h * i, box_w - padding * 2, row_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line,
            )
        painter.restore()

    # ── Slots ──────────────────────────────────────────────────────────────── #

    def eventFilter(self, watched, event: QEvent) -> bool:
        """Enable drag-to-pan and scroll-to-zoom in the preview label."""
        if watched is self._preview_label and self._canvas_widget is not None:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._preview_drag_start = QPointF(event.position())
                return True
            elif t == QEvent.Type.MouseMove and self._preview_drag_start is not None:
                delta = QPointF(event.position()) - self._preview_drag_start
                self._preview_drag_start = QPointF(event.position())
                self._pan_canvas_by_preview_delta(delta.x(), delta.y())
                return True
            elif t == QEvent.Type.MouseButtonRelease:
                self._preview_drag_start = None
                return True
            elif t == QEvent.Type.Wheel:
                c = self._canvas_widget
                if hasattr(c, "set_viewport") and hasattr(c, "_zoom"):
                    delta = event.angleDelta().y()
                    new_zoom = c._zoom + (1 if delta > 0 else -1)
                    c.set_viewport(c.center_lat, c.center_lon, new_zoom)
                    c.repaint()
                    # Delay grab so in-flight tile fetches have time to paint
                    self._preview_timer.start()
                return True
        return super().eventFilter(watched, event)

    def _pan_canvas_by_preview_delta(self, dx: float, dy: float) -> None:
        """Pan the underlying canvas by a drag delta from the preview label."""
        c = self._canvas_widget
        if not (hasattr(c, "px_to_lat_lon") and hasattr(c, "set_viewport")):
            return
        fw, fh = self._preview_frame_w, self._preview_frame_h
        if fw == 0 or fh == 0:
            return
        cw, ch = c.width(), c.height()
        # Map preview-pixel drag to canvas-pixel offset; pan opposes the drag direction
        cx = cw / 2 - dx * cw / fw
        cy = ch / 2 - dy * ch / fh
        new_lat, new_lon = c.px_to_lat_lon(cx, cy)
        c.set_viewport(new_lat, new_lon, c._zoom)
        c.repaint()  # force synchronous repaint before grab
        self._preview_timer.start()

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self._path_edit.setText(path)

    def _on_export(self) -> None:
        path = self._path_edit.text().strip()
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save PDF", "", "PDF Files (*.pdf)"
            )
            if not path:
                return
            self._path_edit.setText(path)
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self._output_path = path
        self._accepted_as = "export"
        self._commit_values()
        self.accept()

    def _on_print(self) -> None:
        self._accepted_as = "print"
        self._commit_values()
        self.accept()

    def _commit_values(self) -> None:
        self._layout.page_size = self._size_combo.currentText()
        self._layout.orientation = PageOrientation(self._orient_combo.currentData())
        self._layout.dpi = self._dpi_spin.value()
        self._layout.capture_zoom = self._zoom_spin.value()

        self._layout.show_legend = self._legend_chk.isChecked()
        self._layout.legend_title = self._legend_title_edit.text().strip()
        hidden: list[str] = []
        labels: dict[str, str] = {}
        for i in range(self._legend_table.rowCount()):
            chk = self._legend_table.item(i, 0)
            lbl = self._legend_table.item(i, 1)
            if chk:
                name = chk.text()
                if chk.checkState() == Qt.CheckState.Unchecked:
                    hidden.append(name)
                if lbl and lbl.text() != name:
                    labels[name] = lbl.text()
        self._layout.legend_hidden_layers = hidden
        self._layout.legend_custom_labels = labels

        self._layout.tb_enabled = self._tb_enabled_chk.isChecked()
        self._layout.tb_project_name = self._tb_project_name_edit.text().strip()
        self._layout.tb_description = self._tb_desc_edit.text().strip()
        self._layout.tb_drawn_by = self._tb_drawn_edit.text().strip()
        self._layout.tb_checked_by = self._tb_checked_edit.text().strip()
        self._layout.tb_revision = self._tb_rev_edit.text().strip()
        self._layout.tb_scale = self._tb_scale_edit.text().strip()
        self._layout.tb_sheet = self._tb_sheet_edit.text().strip()

        self._layout.show_info_box = self._info_chk.isChecked()
        self._layout.info_box_text = self._info_text_edit.toPlainText().strip()
        self._layout.info_box_author = self._info_author_edit.text().strip()
        self._layout.info_box_date = self._info_date_edit.text().strip()

    # ── Properties ────────────────────────────────────────────────────────── #

    @property
    def output_path(self) -> str:
        return self._output_path

    @property
    def accepted_as(self) -> str:
        """'export' or 'print', set after the user clicks the corresponding button."""
        return self._accepted_as
