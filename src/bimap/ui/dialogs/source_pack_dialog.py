"""Source Pack Browser & Import dialog.

Two-mode dialog:
- **Import mode** — user opens a .bsp file, browses its entries, configures
  editable parameters, and adds selected sources to the project.
- **Export mode** — user selects existing project data sources and saves them
  as a redistributable .bsp pack file.

Layout (import mode)
─────────────────────
┌── Pack info bar ─────────────────────────────────────────────────────────┐
│  [Open Pack…]  Pack name / author / description                          │
├── Filter ────────────────────────────────────────────────────────────────┤
│  Category: [All ▼]    Search: [_____________]                            │
├── Source list ───────────────┬── Details / Parameters ───────────────────┤
│  □ Transport Network (WFS)   │  Description …                            │
│  □ Buildings (WFS)           │  ───────────────────────────────────────  │
│  □ Admin Boundaries          │  Editable parameters:                     │
│  □ Hydrography REST          │    Max Features  [500     ]               │
│  …                           │    Bounding Box  [_______]                │
│                              │    CQL Filter    [_______]                │
│                              │                                            │
│                              │    Name in project: [Transport Network ]  │
│                              │                 [Add This Source ▶]        │
├──────────────────────────────┴───────────────────────────────────────────┤
│  [Add All Checked (3)]                              [Close]              │
└──────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from bimap.data.source_pack import PackParam, PackSourceEntry, SourcePack
from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button
from bimap.models.data_source import DataSource


# ── Parameter form widgets ────────────────────────────────────────────────────

class _ParamRow:
    """Wraps a single editable parameter as a labelled form-row widget."""

    def __init__(self, param: PackParam, parent_form: QFormLayout) -> None:
        self._param = param
        if param.param_type == "password":
            self._edit = QLineEdit()
            self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        else:
            self._edit = QLineEdit()
        self._edit.setText(param.value)
        self._edit.setPlaceholderText(param.value)

        hint_parts: list[str] = []
        if param.min_value:
            hint_parts.append(f"{t('min')} {param.min_value}")
        if param.max_value:
            hint_parts.append(f"{t('max')} {param.max_value}")
        if hint_parts:
            self._edit.setToolTip("  ".join(hint_parts))

        parent_form.addRow(param.display_label, self._edit)

    @property
    def name(self) -> str:
        return self._param.name

    @property
    def value(self) -> str:
        return self._edit.text().strip() or self._param.value


# ── Import dialog ─────────────────────────────────────────────────────────────

class SourcePackImportDialog(QDialog):
    """Browse a Source Pack and add entries to the project.

    Parameters
    ----------
    on_add_source:
        Callback invoked with a fully-built ``DataSource`` model whenever the
        user commits an entry.  The caller connects this to the undo-stack
        command that actually adds it to the project.
    initial_pack:
        If provided, the dialog opens with this pack already loaded.
    parent:
        Parent widget.
    """

    def __init__(
        self,
        on_add_source: Callable[[DataSource], None],
        initial_pack: SourcePack | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Import Source Pack"))
        self.setMinimumSize(820, 560)
        self._on_add_source = on_add_source
        self._pack: SourcePack | None = None
        self._param_rows: list[_ParamRow] = []
        self._setup_ui()
        if initial_pack:
            self._load_pack(initial_pack)

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── Top bar: pack info ─────────────────────────────────────────────
        top_bar = QHBoxLayout()
        self._open_btn = QPushButton(t("Open Pack…"))
        self._open_btn.clicked.connect(self._cmd_open_pack)
        top_bar.addWidget(self._open_btn)

        self._pack_info_label = QLabel(t("No pack loaded.  Click 'Open Pack…' to begin."))
        self._pack_info_label.setWordWrap(True)
        self._pack_info_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        top_bar.addWidget(self._pack_info_label, 1)
        root.addLayout(top_bar)

        # ── Filter bar ─────────────────────────────────────────────────────
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel(t("Category:")))
        self._cat_combo = QComboBox()
        self._cat_combo.addItem(t("All"))
        self._cat_combo.currentTextChanged.connect(self._apply_filter)
        filter_bar.addWidget(self._cat_combo)
        filter_bar.addSpacing(12)
        filter_bar.addWidget(QLabel(t("Search:")))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(t("name, tag, description…"))
        self._search_edit.textChanged.connect(self._apply_filter)
        filter_bar.addWidget(self._search_edit, 1)
        root.addLayout(filter_bar)

        # ── Splitter: list | details ───────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: source list with checkboxes
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self._list, 1)

        check_row = QHBoxLayout()
        self._check_all_btn = QPushButton(t("Check All"))
        self._check_all_btn.clicked.connect(self._cmd_check_all)
        self._uncheck_all_btn = QPushButton(t("Uncheck All"))
        self._uncheck_all_btn.clicked.connect(self._cmd_uncheck_all)
        check_row.addWidget(self._check_all_btn)
        check_row.addWidget(self._uncheck_all_btn)
        left_layout.addLayout(check_row)
        splitter.addWidget(left)

        # Right: details + editable params
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        self._desc_browser = QTextBrowser()
        self._desc_browser.setMaximumHeight(90)
        self._desc_browser.setReadOnly(True)
        right_layout.addWidget(self._desc_browser)

        # Fixed params (read-only overview)
        self._fixed_grp = QGroupBox(t("Service configuration (fixed)"))
        self._fixed_layout = QFormLayout(self._fixed_grp)
        right_layout.addWidget(self._fixed_grp)

        # Editable params
        self._edit_grp = QGroupBox(t("Your parameters"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._params_widget = QWidget()
        self._params_form = QFormLayout(self._params_widget)
        scroll.setWidget(self._params_widget)
        edit_grp_layout = QVBoxLayout(self._edit_grp)
        edit_grp_layout.setContentsMargins(4, 4, 4, 4)
        edit_grp_layout.addWidget(scroll)
        right_layout.addWidget(self._edit_grp, 1)

        # Name + single-add row
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(t("Name in project:")))
        self._name_edit = QLineEdit()
        name_row.addWidget(self._name_edit, 1)
        right_layout.addLayout(name_row)

        self._add_one_btn = QPushButton(t("Add This Source ▶"))
        self._add_one_btn.setEnabled(False)
        self._add_one_btn.clicked.connect(self._cmd_add_one)
        right_layout.addWidget(self._add_one_btn)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 1)

        # ── Bottom bar ─────────────────────────────────────────────────────
        bottom = QHBoxLayout()
        self._add_checked_btn = QPushButton(t("Add All Checked (0)"))
        self._add_checked_btn.setEnabled(False)
        self._add_checked_btn.clicked.connect(self._cmd_add_checked)
        bottom.addWidget(self._add_checked_btn)
        bottom.addStretch(1)
        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        add_dialog_help_button(close_box, self, "Import Source Pack window help")
        bottom.addWidget(close_box)
        root.addLayout(bottom)

    # ── Pack loading ──────────────────────────────────────────────────────────

    def _cmd_open_pack(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("Open Source Pack"),
            "",
            t("Source Pack Files (*.bsp *.xml);;All Files (*.*)"),
        )
        if not path:
            return
        try:
            pack = SourcePack.load(path)
        except ValueError as exc:
            QMessageBox.critical(self, t("Error"), str(exc))
            return
        self._load_pack(pack)

    def _load_pack(self, pack: SourcePack) -> None:
        self._pack = pack
        m = pack.meta
        parts = [f"<b>{_esc(m.name)}</b>"]
        if m.author:
            parts.append(f"by {_esc(m.author)}")
        if m.version:
            parts.append(f"v{_esc(m.version)}")
        if m.description:
            parts.append(f"— {_esc(m.description)}")
        if m.license:
            parts.append(f"[{_esc(m.license)}]")
        self._pack_info_label.setText("  ".join(parts))

        # Populate category filter
        self._cat_combo.blockSignals(True)
        self._cat_combo.clear()
        self._cat_combo.addItem(t("All"))
        categories: list[str] = []
        for entry in pack.sources:
            if entry.category and entry.category not in categories:
                categories.append(entry.category)
        for cat in sorted(categories):
            self._cat_combo.addItem(cat)
        self._cat_combo.blockSignals(False)

        self._apply_filter()

    def _apply_filter(self) -> None:
        if self._pack is None:
            return
        cat_filter = self._cat_combo.currentText()
        text_filter = self._search_edit.text().strip()

        self._list.clear()
        for entry in self._pack.sources:
            if cat_filter and cat_filter != t("All") and entry.category != cat_filter:
                continue
            if text_filter and not entry.matches_filter(text_filter):
                continue
            badge = f"[{entry.source_type.upper()}]"
            cat_badge = f"  ({entry.category})" if entry.category else ""
            item = QListWidgetItem(f"{badge} {entry.name}{cat_badge}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(entry.description[:200] if entry.description else "")
            self._list.addItem(item)
        self._refresh_checked_count()

    # ── List interaction ──────────────────────────────────────────────────────

    def _on_select(self, row: int) -> None:
        self._clear_params()
        if row < 0:
            self._add_one_btn.setEnabled(False)
            return
        item = self._list.item(row)
        if item is None:
            return
        entry: PackSourceEntry = item.data(Qt.ItemDataRole.UserRole)
        self._show_entry(entry)

    def _show_entry(self, entry: PackSourceEntry) -> None:
        # Description
        html = f"<b>{_esc(entry.name)}</b>"
        if entry.category:
            html += f"  <i>({_esc(entry.category)})</i>"
        html += f" [{_esc(entry.source_type.upper())}]"
        if entry.description:
            html += f"<br>{_esc(entry.description)}"
        if entry.tags:
            html += f"<br><small>Tags: {_esc(', '.join(entry.tags))}</small>"
        self._desc_browser.setHtml(html)

        # Fixed params (show read-only)
        _clear_layout(self._fixed_layout)
        for p in entry.params:
            if p.fixed and p.value:
                lbl = QLabel(p.value)
                lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                font = QFont()
                font.setFamily("Consolas, monospace")
                lbl.setFont(font)
                self._fixed_layout.addRow(p.display_label, lbl)
        self._fixed_grp.setVisible(self._fixed_layout.rowCount() > 0)

        # Editable params
        _clear_layout(self._params_form)
        self._param_rows = []
        for p in entry.editable_params():
            row = _ParamRow(p, self._params_form)
            self._param_rows.append(row)
        self._edit_grp.setVisible(bool(entry.editable_params()))

        self._name_edit.setText(entry.name)
        self._add_one_btn.setEnabled(True)

    def _clear_params(self) -> None:
        _clear_layout(self._fixed_layout)
        _clear_layout(self._params_form)
        self._param_rows = []
        self._desc_browser.clear()
        self._name_edit.clear()
        self._fixed_grp.setVisible(False)
        self._edit_grp.setVisible(False)

    # ── Check all / none ──────────────────────────────────────────────────────

    def _cmd_check_all(self) -> None:
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Checked)  # type: ignore[union-attr]
        self._refresh_checked_count()

    def _cmd_uncheck_all(self) -> None:
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Unchecked)  # type: ignore[union-attr]
        self._refresh_checked_count()

    def _refresh_checked_count(self) -> None:
        n = sum(
            1
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked  # type: ignore[union-attr]
        )
        self._add_checked_btn.setText(t("Add All Checked ({n})").format(n=n))
        self._add_checked_btn.setEnabled(n > 0 and self._pack is not None)

    # ── Add actions ───────────────────────────────────────────────────────────

    def _cmd_add_one(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        item = self._list.item(row)
        if item is None:
            return
        entry: PackSourceEntry = item.data(Qt.ItemDataRole.UserRole)
        user_vals = {r.name: r.value for r in self._param_rows}
        ds = entry.build_data_source(user_vals, custom_name=self._name_edit.text().strip())
        self._on_add_source(ds)
        # Visual feedback: tick the item
        item.setCheckState(Qt.CheckState.Checked)
        self._refresh_checked_count()

    def _cmd_add_checked(self) -> None:
        added = 0
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                continue
            entry: PackSourceEntry = item.data(Qt.ItemDataRole.UserRole)
            # Use default values for all editable params on bulk-add
            ds = entry.build_data_source()
            self._on_add_source(ds)
            added += 1
        if added:
            QMessageBox.information(
                self,
                t("Sources Added"),
                t("{n} data source(s) added to the project.").format(n=added),
            )


# ── Export dialog ─────────────────────────────────────────────────────────────

class SourcePackExportDialog(QDialog):
    """Select project data sources to bundle and save as a .bsp pack file.

    Parameters
    ----------
    sources:
        List of ``DataSource`` models from the current project.
    parent:
        Parent widget.
    """

    def __init__(
        self,
        sources: list[DataSource],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Export Source Pack"))
        self.setMinimumSize(560, 440)
        self._sources = sources
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        # Pack metadata
        meta_grp = QGroupBox(t("Pack information"))
        meta_form = QFormLayout(meta_grp)
        self._pack_name_edit = QLineEdit()
        self._pack_name_edit.setPlaceholderText(t("e.g. Spain Open Data"))
        meta_form.addRow(t("Pack name"), self._pack_name_edit)
        self._author_edit = QLineEdit()
        meta_form.addRow(t("Author"), self._author_edit)
        self._desc_edit = QLineEdit()
        meta_form.addRow(t("Description"), self._desc_edit)
        self._version_edit = QLineEdit("1.0.0")
        meta_form.addRow(t("Version"), self._version_edit)
        self._license_edit = QLineEdit()
        self._license_edit.setPlaceholderText("OGL / CC-BY / etc.")
        meta_form.addRow(t("License"), self._license_edit)
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://…")
        meta_form.addRow(t("URL"), self._url_edit)
        root.addWidget(meta_grp)

        # Source selection
        sel_grp = QGroupBox(t("Select sources to include"))
        sel_layout = QVBoxLayout(sel_grp)
        self._source_list = QListWidget()
        for ds in self._sources:
            item = QListWidgetItem(f"[{ds.source_type.upper()}] {ds.name}")
            item.setData(Qt.ItemDataRole.UserRole, ds)
            item.setCheckState(Qt.CheckState.Checked)
            self._source_list.addItem(item)
        sel_layout.addWidget(self._source_list)
        root.addWidget(sel_grp, 1)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._cmd_save)
        btn_box.rejected.connect(self.reject)
        add_dialog_help_button(btn_box, self, "Export Source Pack window help")
        root.addWidget(btn_box)

    def _cmd_save(self) -> None:
        pack_name = self._pack_name_edit.text().strip() or "My Source Pack"
        selected: list[DataSource] = []
        for i in range(self._source_list.count()):
            item = self._source_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))

        if not selected:
            QMessageBox.warning(self, t("Nothing selected"), t("Choose at least one source."))
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            t("Save Source Pack"),
            f"{pack_name.replace(' ', '_')}.bsp",
            t("Source Pack Files (*.bsp);;XML Files (*.xml)"),
        )
        if not path:
            return

        from bimap.data.source_pack import PackParam, PackSourceEntry, SourcePackMeta

        meta = SourcePackMeta(
            name=pack_name,
            author=self._author_edit.text().strip(),
            description=self._desc_edit.text().strip(),
            version=self._version_edit.text().strip() or "1.0.0",
            url=self._url_edit.text().strip(),
            license=self._license_edit.text().strip(),
        )
        entries: list[PackSourceEntry] = []
        for ds in selected:
            params = [
                PackParam(name=k, value=v, fixed=True)
                for k, v in ds.connection.items()
            ]
            entries.append(
                PackSourceEntry(
                    id=str(ds.id),
                    name=ds.name,
                    source_type=ds.source_type.value,
                    params=params,
                )
            )
        from bimap.data.source_pack import SourcePack
        pack = SourcePack(meta=meta, sources=entries)
        try:
            SourcePack.save(pack, path)
        except OSError as exc:
            QMessageBox.critical(self, t("Error"), str(exc))
            return
        QMessageBox.information(
            self,
            t("Pack saved"),
            t("Source pack saved to:\n{path}").format(path=path),
        )
        self.accept()


# ── Utilities ─────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _clear_layout(layout: QFormLayout) -> None:
    """Remove all rows from a QFormLayout."""
    while layout.rowCount():
        layout.removeRow(0)
