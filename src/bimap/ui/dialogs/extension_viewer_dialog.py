"""In-app floating HTML5/CSS/JS extension viewer.

Opens the rendered extension inside a resizable BIMAP dialog using
``QWebEngineView`` when available, otherwise opens in the system browser and
shows a status message in the dialog.
"""

from __future__ import annotations

import json
import tempfile
import webbrowser
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import add_top_right_help_button, show_help_dialog
from bimap.ui.dialogs.extension_editor_dialog import _build_data_payload

# Try to import QWebEngineView — it requires PyQtWebEngine which is optional
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore
    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False


def _data_dir_url() -> QUrl:
    """Return a file:// QUrl pointing to the bimap/data package directory.
    Setting this as the base URL in setHtml() allows relative-path resources
    (e.g. chart.min.js) to be loaded from the bundled package data."""
    try:
        import importlib.resources
        pkg_data = importlib.resources.files("bimap.data")
        # Resolve to a real filesystem path
        ctx = importlib.resources.as_file(pkg_data)
        data_path = ctx.__enter__()   # type: ignore[attr-defined]
        return QUrl.fromLocalFile(str(data_path) + "/")
    except Exception:
        return QUrl("about:blank")


def _build_rendered_html(element: Any, etype: str) -> str:
    """Inject BIMAP_DATA into the element's extension_html and return the full document."""
    html_template: str = getattr(element, "extension_html", "").strip()
    if not html_template:
        raise ValueError(t("No extension configured for this element."))

    payload = _build_data_payload(element, etype)
    data_js = json.dumps(payload, ensure_ascii=False, indent=2)
    injection = f"<script>\nconst BIMAP_DATA = {data_js};\n</script>\n"

    if "</head>" in html_template:
        return html_template.replace("</head>", injection + "</head>", 1)
    return injection + html_template


class ExtensionViewerDialog(QDialog):
    """Floating dialog that renders an element's HTML extension in-app.

    If ``PyQtWebEngine`` is not installed the rendered HTML is written to a
    temp file and opened in the system browser instead, while the dialog shows
    an informational label.
    """

    def __init__(
        self,
        element: Any,
        etype: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        name = getattr(element, "name", str(getattr(element, "id", "")))
        self.setWindowTitle(f"{t('View Extension')} — {name}")
        self.resize(860, 640)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self._element = element
        self._etype = etype
        self._tmp_path: str | None = None
        self._setup_ui()

    # ── Setup ──────────────────────────────────────────────────────────────── #

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        add_top_right_help_button(self, self._show_help)

        try:
            rendered = _build_rendered_html(self._element, self._etype)
        except ValueError as exc:
            lbl = QLabel(str(exc))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #888888; font-style: italic; padding: 24px;")
            layout.addWidget(lbl)
            return

        if _WEBENGINE_AVAILABLE:
            self._web = QWebEngineView()
            self._web.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            # Set dark page background to prevent white flash on load
            from PyQt6.QtGui import QColor as _QColor
            page = self._web.page()
            page.setBackgroundColor(_QColor("#1e1e2e"))
            # Reject any fullscreen request from the page to prevent the dialog
            # briefly expanding to fill the screen on first load (Qt/WebEngine bug)
            try:
                page.fullScreenRequested.connect(lambda req: req.reject())
            except AttributeError:
                pass
            self._web.setHtml(rendered, _data_dir_url())
            layout.addWidget(self._web, 1)

            # Reload / Open-in-Browser toolbar
            btn_row_widget = QWidget()
            btn_row_widget.setStyleSheet("background: #252526; padding: 4px;")
            from PyQt6.QtWidgets import QHBoxLayout
            btn_row = QHBoxLayout(btn_row_widget)
            btn_row.setContentsMargins(8, 2, 8, 2)
            btn_reload = QPushButton("↺ " + t("Reload"))
            btn_reload.clicked.connect(self._reload)
            btn_browser = QPushButton(t("Open in Browser"))
            btn_browser.clicked.connect(self._open_in_browser)
            btn_row.addWidget(btn_reload)
            btn_row.addStretch()
            btn_row.addWidget(btn_browser)
            layout.addWidget(btn_row_widget)
        else:
            # Fallback: open in system browser
            self._open_in_browser_from(rendered)
            info = QLabel(
                "<b>PyQtWebEngine not installed.</b><br>"
                "The extension has been opened in your system browser.<br>"
                "<small>Install <code>PyQtWebEngine</code> for in-app viewing.</small>"
            )
            info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info.setTextFormat(Qt.TextFormat.RichText)
            info.setStyleSheet("padding: 32px; color: #d4d4d4;")
            layout.addWidget(info)

            btn_reopen = QPushButton(t("Open in Browser"))
            btn_reopen.clicked.connect(lambda: self._open_in_browser_from(rendered))
            btn_reopen.setMaximumWidth(200)
            from PyQt6.QtWidgets import QHBoxLayout
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(btn_reopen)
            row.addStretch()
            layout.addLayout(row)

    def _show_help(self) -> None:
        show_help_dialog(self, t("Application Help"), t("Extension Viewer window help"))

    # ── Slots / helpers ────────────────────────────────────────────────────── #

    def _reload(self) -> None:
        """Re-build and reload from current element data (picks up metadata changes)."""
        try:
            rendered = _build_rendered_html(self._element, self._etype)
        except ValueError:
            return
        if _WEBENGINE_AVAILABLE and hasattr(self, "_web"):
            from PyQt6.QtGui import QColor as _QColor
            self._web.page().setBackgroundColor(_QColor("#1e1e2e"))
            self._web.setHtml(rendered, _data_dir_url())

    def _open_in_browser(self) -> None:
        try:
            rendered = _build_rendered_html(self._element, self._etype)
        except ValueError:
            return
        self._open_in_browser_from(rendered)

    def _open_in_browser_from(self, rendered: str) -> None:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".html", mode="w", encoding="utf-8", delete=False
        )
        tmp.write(rendered)
        tmp.close()
        self._tmp_path = tmp.name
        webbrowser.open(Path(tmp.name).as_uri())

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Clean up temporary file on close."""
        if self._tmp_path:
            try:
                Path(self._tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
        super().closeEvent(event)
