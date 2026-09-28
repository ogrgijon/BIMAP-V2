"""Debug log dialog — hidden feature accessible via triple-clicking About.

Captures Python ``logging`` records (WARNING level and above by default) and
displays them in a read-only plain-text widget.  Records are accumulated in an
in-memory list so they survive across dialog opens.
"""
from __future__ import annotations

import logging
import traceback
from typing import ClassVar

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button


# ── In-memory log handler ──────────────────────────────────────────────────────

class _MemoryHandler(logging.Handler):
    """Accumulates up to *maxlen* formatted log records in a class-level list."""

    _records: ClassVar[list[str]] = []
    _maxlen: ClassVar[int] = 2000
    _instance: ClassVar["_MemoryHandler | None"] = None

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            msg = self.format(record)
            if record.exc_info:
                msg += "\n" + "".join(traceback.format_exception(*record.exc_info))
            _MemoryHandler._records.append(msg)
            if len(_MemoryHandler._records) > self._maxlen:
                _MemoryHandler._records = _MemoryHandler._records[-self._maxlen :]
        except Exception:  # noqa: BLE001
            pass

    @classmethod
    def install(cls) -> "_MemoryHandler":
        """Install the handler on the root logger (idempotent)."""
        if cls._instance is None:
            h = cls()
            h.setLevel(logging.DEBUG)
            fmt = logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
                datefmt="%H:%M:%S",
            )
            h.setFormatter(fmt)
            logging.getLogger().addHandler(h)
            # Ensure root logger passes DEBUG records through
            root = logging.getLogger()
            if root.level == logging.NOTSET or root.level > logging.DEBUG:
                root.setLevel(logging.DEBUG)
            cls._instance = h
        return cls._instance


# Install immediately on module import so records are captured from startup.
_MemoryHandler.install()


# ── Dialog ─────────────────────────────────────────────────────────────────────

class DebugLogDialog(QDialog):
    """Read-only scrollable view of captured Python logging records."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Debug Log")
        self.resize(900, 550)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
        )

        layout = QVBoxLayout(self)

        # Header
        hdr = QLabel(
            "<b>Debug Log</b> — all Python logging records captured since startup"
            "<br><small>Triple-click <i>About</i> again to reopen. "
            "Level: DEBUG and above.</small>"
        )
        hdr.setWordWrap(True)
        layout.addWidget(hdr)

        # Log text area
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Consolas", 9))
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._refresh()
        layout.addWidget(self._text)

        # Button row
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        refresh_btn = QPushButton(t("Refresh"))
        refresh_btn.setToolTip(t("Refresh the debug log contents"))
        refresh_btn.clicked.connect(self._refresh)
        btn_layout.addWidget(refresh_btn)

        clear_btn = QPushButton(t("Clear"))
        clear_btn.setToolTip(t("Clear the debug log"))
        clear_btn.clicked.connect(self._clear)
        btn_layout.addWidget(clear_btn)

        copy_btn = QPushButton(t("Copy All"))
        copy_btn.setToolTip(t("Copy the complete debug log to the clipboard"))
        copy_btn.clicked.connect(self._copy_all)
        btn_layout.addWidget(copy_btn)

        btn_layout.addStretch()

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bbox.rejected.connect(self.reject)
        add_dialog_help_button(bbox, self, "Debug Log window help")
        btn_layout.addWidget(bbox)

        layout.addWidget(btn_row)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        records = _MemoryHandler._records
        if records:
            self._text.setPlainText("\n".join(records))
            # Scroll to bottom
            sb = self._text.verticalScrollBar()
            if sb is not None:
                sb.setValue(sb.maximum())
        else:
            self._text.setPlainText("(no records yet)")

    def _clear(self) -> None:
        _MemoryHandler._records.clear()
        self._text.setPlainText("(log cleared)")

    def _copy_all(self) -> None:
        from PyQt6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(self._text.toPlainText())
