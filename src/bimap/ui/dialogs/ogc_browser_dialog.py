"""OGC Catalogue Browser dialog.

Lets the user search an OGC CSW endpoint (default: IDEE Spain) and add
discovered WFS services as data sources in the current project.

Layout
------
┌─── Catalog URL ───────────────────────── [Connect] ──┐
│  ┌──────────────── Search ────────────────────────┐   │
│  │  text box                    [Search]          │   │
│  └──────────────────────────────────────────────── │   │
│                                                      │
│  ┌──── Results ─────────────────────────────────┐   │
│  │  QListWidget  (title + service badge)        │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──── Details ─────────────────────────────────┐   │
│  │  Title / Abstract / BBox / Access URL        │   │
│  │              [Add as WFS Data Source]        │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
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
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from bimap.data.csw_catalog import IDEE_CSW_URL, CswCatalog, CswRecord
from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button


# ── Background worker ─────────────────────────────────────────────────────────

class _SearchWorker(QThread):
    finished = pyqtSignal(list)   # list[CswRecord]
    error = pyqtSignal(str)

    def __init__(
        self,
        catalog_url: str,
        text: str,
        max_records: int = 20,
    ) -> None:
        super().__init__()
        self._url = catalog_url
        self._text = text
        self._max_records = max_records

    def run(self) -> None:
        try:
            cat = CswCatalog(self._url)
            records = cat.search(self._text, max_records=self._max_records)
            self.finished.emit(records)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


# ── Dialog ────────────────────────────────────────────────────────────────────

class OgcBrowserDialog(QDialog):
    """Browse an OGC CSW catalogue and add services as data sources.

    Parameters
    ----------
    on_add_wfs:
        Callback invoked with ``(url, type_name)`` when the user clicks
        "Add as WFS Data Source".  It is the caller's responsibility to
        open the DataSourceDialog pre-filled.
    parent:
        Parent widget.
    """

    def __init__(
        self,
        on_add_wfs: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Browse OGC Catalog"))
        self.setMinimumSize(700, 540)
        self._wfs_add_callback = on_add_wfs
        self._records: list[CswRecord] = []
        self._worker: _SearchWorker | None = None
        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── Catalog URL row ───────────────────────────────────────────────
        url_grp = QGroupBox(t("Catalog endpoint"))
        url_row = QHBoxLayout(url_grp)
        self._url_edit = QLineEdit(IDEE_CSW_URL)
        self._url_edit.setPlaceholderText("https://…/csw")
        self._url_edit.setToolTip(t("CSW catalog endpoint used to search datasets"))
        self._connect_btn = QPushButton(t("Connect"))
        self._connect_btn.setToolTip(t("Connect to the catalog endpoint"))
        self._connect_btn.clicked.connect(self._on_connect)
        url_row.addWidget(self._url_edit, 1)
        url_row.addWidget(self._connect_btn)
        root.addWidget(url_grp)

        # ── Search row ────────────────────────────────────────────────────
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(t("Search datasets…"))
        self._search_edit.setToolTip(t("Search the connected catalog by title or keywords"))
        self._search_edit.returnPressed.connect(self._on_search)
        self._search_btn = QPushButton(t("Search"))
        self._search_btn.setToolTip(t("Search the catalog"))
        self._search_btn.setDefault(True)
        self._search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self._search_edit, 1)
        search_row.addWidget(self._search_btn)
        root.addLayout(search_row)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._status_label)

        # ── Splitter: results | details ───────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.currentRowChanged.connect(self._on_select)
        splitter.addWidget(self._list)

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_browser = QTextBrowser()
        self._detail_browser.setReadOnly(True)
        self._detail_browser.setOpenExternalLinks(True)
        detail_layout.addWidget(self._detail_browser, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._add_wfs_btn = QPushButton(t("Add as WFS Data Source"))
        self._add_wfs_btn.setToolTip(t("Create a WFS data source from the selected catalog record"))
        self._add_wfs_btn.setEnabled(False)
        self._add_wfs_btn.clicked.connect(self._on_add_wfs)
        btn_row.addWidget(self._add_wfs_btn)
        detail_layout.addLayout(btn_row)
        splitter.addWidget(detail_widget)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # ── Close button ──────────────────────────────────────────────────
        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        add_dialog_help_button(close_box, self, "Browse OGC Catalog window help")
        root.addWidget(close_box)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_connect(self) -> None:
        url = self._url_edit.text().strip()
        if not url:
            return
        self._status_label.setText(t("Connecting…"))
        self._connect_btn.setEnabled(False)
        self._search_btn.setEnabled(False)
        try:
            cat = CswCatalog(url)
            info = cat.get_capabilities()
            title = info.get("title") or url
            self._status_label.setText(f"Connected: {title}")
        except Exception as exc:  # noqa: BLE001
            self._status_label.setText(f"Error: {exc}")
        finally:
            self._connect_btn.setEnabled(True)
            self._search_btn.setEnabled(True)

    def _on_search(self) -> None:
        url = self._url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, t("No URL"), t("Enter a catalog URL first."))
            return
        text = self._search_edit.text().strip()
        self._status_label.setText(t("Searching…"))
        self._list.clear()
        self._records = []
        self._detail_browser.clear()
        self._add_wfs_btn.setEnabled(False)
        self._search_btn.setEnabled(False)
        self._worker = _SearchWorker(url, text)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, records: list[CswRecord]) -> None:
        self._records = records
        self._search_btn.setEnabled(True)
        if not records:
            self._status_label.setText(t("No results found."))
            return
        self._status_label.setText(
            t("{n} results").format(n=len(records))
        )
        for rec in records:
            badge = f"[{rec.service_type}]" if rec.service_type else ""
            item = QListWidgetItem(f"{badge} {rec.title}".strip())
            item.setToolTip(rec.abstract[:200] if rec.abstract else "")
            self._list.addItem(item)

    def _on_error(self, msg: str) -> None:
        self._search_btn.setEnabled(True)
        self._status_label.setText(f"Error: {msg}")

    def _on_select(self, row: int) -> None:
        if row < 0 or row >= len(self._records):
            self._detail_browser.clear()
            self._add_wfs_btn.setEnabled(False)
            return
        rec = self._records[row]
        html_parts = [f"<h3>{_esc(rec.title)}</h3>"]
        if rec.service_type:
            html_parts.append(f"<p><b>Service type:</b> {_esc(rec.service_type)}</p>")
        if rec.abstract:
            html_parts.append(f"<p>{_esc(rec.abstract)}</p>")
        if rec.access_url:
            html_parts.append(
                f'<p><b>Access URL:</b> <a href="{_esc(rec.access_url)}">'
                f"{_esc(rec.access_url)}</a></p>"
            )
        if rec.bbox:
            mn, my, mx, mxy = rec.bbox
            html_parts.append(
                f"<p><b>Bounding box:</b> {mn:.4f}, {my:.4f} → {mx:.4f}, {mxy:.4f}</p>"
            )
        self._detail_browser.setHtml("".join(html_parts))
        # Enable "Add as WFS" only when a WFS service is selected
        self._add_wfs_btn.setEnabled(bool(rec.access_url or rec.is_wfs()))

    def _on_add_wfs(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._records):
            return
        rec = self._records[row]
        url = rec.access_url
        if not url:
            QMessageBox.information(
                self,
                t("No URL"),
                t("No base service URL found for this record.\n"
                  "Copy the access URL manually and add a WFS data source."),
            )
            return
        if self._wfs_add_callback is not None:
            self._wfs_add_callback(url, "")
        else:
            QMessageBox.information(
                self,
                t("WFS URL"),
                t("Copy this endpoint URL into a new WFS data source:\n\n{url}").format(
                    url=url
                ),
            )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )
