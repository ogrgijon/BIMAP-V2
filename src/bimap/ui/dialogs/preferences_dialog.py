"""Preferences dialog — Edit → Preferences… (Ctrl+,).

Layout: QListWidget (categories, left) + QStackedWidget (pages, right)
+ QDialogButtonBox (OK / Cancel / Apply).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bimap.config import (
    DEFAULT_CENTER_LAT,
    DEFAULT_CENTER_LON,
    DEFAULT_TILE_PROVIDER,
    DEFAULT_ZOOM,
    Settings,
    TILE_PROVIDERS,
    load_user_settings,
    save_user_settings,
)
from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button


class PreferencesDialog(QDialog):
    """Category-switcher preferences dialog."""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle(t("Preferences"))
        self.setMinimumSize(700, 500)
        self._build_ui()
        self._populate(settings)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)

        # ── Category list (left) ─────────────────────────────────────────────
        self._cat_list = QListWidget()
        self._cat_list.setFixedWidth(155)
        self._cat_list.setStyleSheet(
            "QListWidget { background: #252526; border: none;"
            " border-right: 1px solid #3c3c3c; }"
            "QListWidget::item { padding: 11px 16px; color: #cccccc; }"
            "QListWidget::item:selected { background: #37373d; color: #ffffff;"
            " border-left: 3px solid #007acc; }"
        )
        for name in [
            t("General"),
            t("Map"),
            t("Cache"),
            t("Appearance"),
            t("Advanced"),
            t("Live Feeds"),
        ]:
            self._cat_list.addItem(QListWidgetItem(name))
        self._cat_list.setCurrentRow(0)

        # ── Pages (stacked, right) ────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._page_general = self._make_general_page()
        self._page_map = self._make_map_page()
        self._page_cache = self._make_cache_page()
        self._page_appearance = self._make_appearance_page()
        self._page_advanced = self._make_advanced_page()
        self._page_live_feeds = self._make_live_feeds_page()
        for page in (
            self._page_general,
            self._page_map,
            self._page_cache,
            self._page_appearance,
            self._page_advanced,
            self._page_live_feeds,
        ):
            self._stack.addWidget(page)

        self._cat_list.currentRowChanged.connect(self._stack.setCurrentIndex)

        right_panel = QWidget()
        rl = QVBoxLayout(right_panel)
        rl.setContentsMargins(20, 16, 20, 16)
        rl.addWidget(self._stack)

        middle.addWidget(self._cat_list)
        middle.addWidget(right_panel, 1)

        # ── Button box ───────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply,
        )
        btn_box.setContentsMargins(16, 8, 16, 12)
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        add_dialog_help_button(btn_box, self, "Preferences window help")
        btn_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)

        outer.addLayout(middle, 1)
        outer.addWidget(btn_box)

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _make_general_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem(t("English"), "en")
        self._lang_combo.addItem(t("Spanish"), "es")
        form.addRow(t("Language") + ":", self._lang_combo)

        self._autosave_spin = QSpinBox()
        self._autosave_spin.setRange(10, 600)
        self._autosave_spin.setSuffix(" s")
        self._autosave_spin.setToolTip(t("Autosave interval in seconds (10–600)"))
        form.addRow(t("Autosave interval") + ":", self._autosave_spin)

        self._undo_spin = QSpinBox()
        self._undo_spin.setRange(10, 500)
        self._undo_spin.setToolTip(t("Maximum number of undo steps (10–500)"))
        form.addRow(t("Undo stack limit") + ":", self._undo_spin)

        self._startup_combo = QComboBox()
        self._startup_combo.addItem(t("Empty project"), "none")
        self._startup_combo.addItem(t("Reopen last project"), "last")
        form.addRow(t("On startup") + ":", self._startup_combo)

        return page

    def _make_map_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._zoom_spin = QSpinBox()
        self._zoom_spin.setRange(1, 19)
        form.addRow(t("Default zoom") + ":", self._zoom_spin)

        self._lat_spin = QDoubleSpinBox()
        self._lat_spin.setRange(-90.0, 90.0)
        self._lat_spin.setDecimals(6)
        form.addRow(t("Default latitude") + ":", self._lat_spin)

        self._lon_spin = QDoubleSpinBox()
        self._lon_spin.setRange(-180.0, 180.0)
        self._lon_spin.setDecimals(6)
        form.addRow(t("Default longitude") + ":", self._lon_spin)

        self._provider_combo = QComboBox()
        for key, info in TILE_PROVIDERS.items():
            self._provider_combo.addItem(info["label"], key)
        form.addRow(t("Tile provider") + ":", self._provider_combo)

        self._provider_url_label = QLabel()
        self._provider_url_label.setWordWrap(True)
        self._provider_url_label.setStyleSheet("color: #858585; font-size: 10px;")
        form.addRow("", self._provider_url_label)
        self._provider_combo.currentIndexChanged.connect(self._update_provider_preview)

        self._scale_bar_check = QCheckBox(t("Show scale bar"))
        form.addRow("", self._scale_bar_check)

        self._north_arrow_check = QCheckBox(t("Show north arrow"))
        form.addRow("", self._north_arrow_check)

        self._grid_scale_combo = QComboBox()
        for label, val in [
            (t("Fine (0.5×)"),       0.5),
            (t("Normal (1×)"),       1.0),
            (t("Coarse (2×)"),       2.0),
            (t("Very Coarse (4×)"),  4.0),
        ]:
            self._grid_scale_combo.addItem(label, val)
        form.addRow(t("Grid size") + ":", self._grid_scale_combo)

        return page

    def _make_cache_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._cache_size_spin = QSpinBox()
        self._cache_size_spin.setRange(128, 2048)
        self._cache_size_spin.setSingleStep(128)
        self._cache_size_spin.setSuffix(" MB")
        form.addRow(t("Max tile cache size") + ":", self._cache_size_spin)

        self._cache_expiry_spin = QSpinBox()
        self._cache_expiry_spin.setRange(1, 90)
        self._cache_expiry_spin.setSuffix(t(" days"))
        form.addRow(t("Tile expiry") + ":", self._cache_expiry_spin)

        note = QLabel(t("Cache size and expiry take effect on next launch."))
        note.setStyleSheet("color: #858585; font-size: 10px;")
        note.setWordWrap(True)
        form.addRow("", note)

        clear_row = QHBoxLayout()
        self._cache_size_label = QLabel()
        btn_clear = QPushButton(t("Clear cache now"))
        btn_clear.clicked.connect(self._on_clear_cache)
        clear_row.addWidget(self._cache_size_label)
        clear_row.addStretch()
        clear_row.addWidget(btn_clear)
        form.addRow("", clear_row)
        self._refresh_cache_size_label()

        return page

    def _make_appearance_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._keypoint_font_combo = QFontComboBox()
        self._keypoint_font_combo.setToolTip(t("Font used by font icons in keypoints"))
        form.addRow(t("Keypoint icon font") + ":", self._keypoint_font_combo)
        return page

    def _make_advanced_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._projects_dir_edit, proj_row = self._make_path_row()
        form.addRow(t("Projects folder") + ":", proj_row)

        form.addRow(QLabel(""))   # spacer
        reset_btn = QPushButton(t("Reset all to defaults"))
        reset_btn.setStyleSheet("QPushButton { color: #f44747; }")
        reset_btn.clicked.connect(self._on_reset_defaults)
        form.addRow("", reset_btn)

        return page

    def _make_live_feeds_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._live_timeout_spin = QSpinBox()
        self._live_timeout_spin.setRange(1, 60)
        self._live_timeout_spin.setSuffix(" s")
        self._live_timeout_spin.setValue(10)
        self._live_timeout_spin.setToolTip(t("live_timeout_tip"))
        form.addRow(t("live_network_timeout") + ":", self._live_timeout_spin)

        self._live_max_markers_spin = QSpinBox()
        self._live_max_markers_spin.setRange(100, 50_000)
        self._live_max_markers_spin.setSingleStep(100)
        self._live_max_markers_spin.setValue(5000)
        form.addRow(t("live_max_markers") + ":", self._live_max_markers_spin)

        self._live_trail_spin = QSpinBox()
        self._live_trail_spin.setRange(0, 100)
        self._live_trail_spin.setValue(0)
        self._live_trail_spin.setSpecialValueText(t("trail_off"))
        form.addRow(t("live_trail_default") + ":", self._live_trail_spin)

        self._live_follow_chk = QCheckBox(t("live_follow_fastest"))
        form.addRow("", self._live_follow_chk)

        self._live_error_badge_chk = QCheckBox(t("live_show_error_badge"))
        self._live_error_badge_chk.setChecked(True)
        form.addRow("", self._live_error_badge_chk)

        return page

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_path_row(self) -> tuple[QLineEdit, QWidget]:
        container = QWidget()
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setPlaceholderText(t("(default)"))
        btn = QPushButton(t("Browse…"))
        btn.setFixedWidth(80)
        btn.clicked.connect(lambda: self._browse_dir(edit))
        hbox.addWidget(edit)
        hbox.addWidget(btn)
        return edit, container

    def _browse_dir(self, edit: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, t("Choose folder"), edit.text() or str(Path.home())
        )
        if folder:
            edit.setText(folder)

    def _update_provider_preview(self) -> None:
        key = self._provider_combo.currentData()
        if key and key in TILE_PROVIDERS:
            self._provider_url_label.setText(TILE_PROVIDERS[key]["url"])

    def _refresh_cache_size_label(self) -> None:
        try:
            from bimap.ui.map_canvas.tile_cache import get_tile_cache
            size_mb = get_tile_cache()._cache.volume() / (1024 * 1024)
            self._cache_size_label.setText(f"{t('Current size')}: {size_mb:.1f} MB")
        except Exception:
            self._cache_size_label.setText("")

    def _on_clear_cache(self) -> None:
        try:
            from bimap.ui.map_canvas.tile_cache import get_tile_cache
            get_tile_cache()._cache.clear()
            self._refresh_cache_size_label()
        except Exception:
            pass

    def _on_reset_defaults(self) -> None:
        if (
            QMessageBox.question(
                self,
                t("Reset all to defaults"),
                t("Reset all preferences to their default values?"),
            )
            == QMessageBox.StandardButton.Yes
        ):
            self._populate(Settings())

    # ── Populate / collect ────────────────────────────────────────────────────

    def _populate(self, s: Settings) -> None:
        # General
        idx = self._lang_combo.findData(s.language)
        self._lang_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._autosave_spin.setValue(s.autosave_interval_ms // 1000)
        self._undo_spin.setValue(s.undo_stack_limit)
        idx2 = self._startup_combo.findData(s.startup_mode)
        self._startup_combo.setCurrentIndex(idx2 if idx2 >= 0 else 0)
        # Map
        self._zoom_spin.setValue(s.default_zoom)
        self._lat_spin.setValue(s.default_lat)
        self._lon_spin.setValue(s.default_lon)
        idx3 = self._provider_combo.findData(s.tile_provider)
        self._provider_combo.setCurrentIndex(idx3 if idx3 >= 0 else 0)
        self._update_provider_preview()
        self._scale_bar_check.setChecked(s.show_scale_bar)
        self._north_arrow_check.setChecked(s.show_north_arrow)
        # grid scale
        gs_idx = self._grid_scale_combo.findData(s.grid_scale)
        self._grid_scale_combo.setCurrentIndex(gs_idx if gs_idx >= 0 else 1)
        # Cache
        self._cache_size_spin.setValue(s.tile_cache_max_mb)
        self._cache_expiry_spin.setValue(s.tile_cache_expiry_days)
        # Advanced
        self._projects_dir_edit.setText(s.projects_dir)
        if s.keypoint_icon_font_family:
            self._keypoint_font_combo.setCurrentFont(QFont(s.keypoint_icon_font_family))
        # Live Feeds
        self._live_timeout_spin.setValue(s.live_network_timeout_s)
        self._live_max_markers_spin.setValue(s.live_max_markers)
        self._live_trail_spin.setValue(s.live_trail_default)
        self._live_follow_chk.setChecked(s.live_follow_fastest)
        self._live_error_badge_chk.setChecked(s.live_show_error_badge)

    def _collect(self) -> Settings:
        return Settings(
            language=self._lang_combo.currentData() or "en",
            autosave_interval_ms=self._autosave_spin.value() * 1000,
            undo_stack_limit=self._undo_spin.value(),
            startup_mode=self._startup_combo.currentData() or "none",
            default_zoom=self._zoom_spin.value(),
            default_lat=self._lat_spin.value(),
            default_lon=self._lon_spin.value(),
            tile_provider=self._provider_combo.currentData() or DEFAULT_TILE_PROVIDER,
            show_scale_bar=self._scale_bar_check.isChecked(),
            show_north_arrow=self._north_arrow_check.isChecked(),
            grid_scale=float(self._grid_scale_combo.currentData() or 1.0),
            tile_cache_max_mb=self._cache_size_spin.value(),
            tile_cache_expiry_days=self._cache_expiry_spin.value(),
            projects_dir=self._projects_dir_edit.text(),
            keypoint_icon_font_family=self._keypoint_font_combo.currentFont().family(),
            live_network_timeout_s=self._live_timeout_spin.value(),
            live_max_markers=self._live_max_markers_spin.value(),
            live_trail_default=self._live_trail_spin.value(),
            live_follow_fastest=self._live_follow_chk.isChecked(),
            live_show_error_badge=self._live_error_badge_chk.isChecked(),
        )

    # ── OK / Apply ────────────────────────────────────────────────────────────

    def _on_apply(self) -> None:
        self._settings = self._collect()
        save_user_settings(self._settings)

    def _on_ok(self) -> None:
        self._on_apply()
        self.accept()

    def get_settings(self) -> Settings:
        return self._settings
