"""Background data-refresh scheduler using QThread."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from bimap.data.base import DataSourceBase
from bimap.models.data_source import DataSource, RefreshMode


class RefreshWorker(QObject):
    """Runs in a QThread — fetches data without blocking the UI."""

    finished = pyqtSignal(str, list)    # source_id, rows
    error = pyqtSignal(str, str)        # source_id, error_message
    stats = pyqtSignal(str, int, int)   # source_id, row_count, duration_ms

    def __init__(self, source_id: str, connector: DataSourceBase) -> None:
        super().__init__()
        self._source_id = source_id
        self._connector = connector

    def run(self) -> None:
        t0 = time.monotonic()
        try:
            self._connector.connect()
            rows = self._connector.fetch()
            ms = int((time.monotonic() - t0) * 1000)
            self.finished.emit(self._source_id, rows)
            self.stats.emit(self._source_id, len(rows), ms)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(self._source_id, str(exc))
        finally:
            try:
                self._connector.disconnect()
            except Exception:  # noqa: BLE001
                pass


class DataRefreshManager(QObject):
    """
    Manages refresh timers and worker threads for all DataSource models.
    Emit *data_refreshed(source_id, rows)* when new data arrives.
    Emit *refresh_error(source_id, message)* on failure.
    """

    data_refreshed = pyqtSignal(str, list)   # source_id (str UUID), rows
    refresh_error = pyqtSignal(str, str)     # source_id, message
    refresh_started = pyqtSignal(str)        # source_id
    refresh_stats = pyqtSignal(str, int, int)  # source_id, row_count, duration_ms

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timers: dict[str, QTimer] = {}
        self._threads: dict[str, QThread] = {}
        self._connectors: dict[str, DataSourceBase] = {}

    def register(self, ds: DataSource, connector: DataSourceBase) -> None:
        """Register a data source and start its timer if needed."""
        sid = str(ds.id)
        self._connectors[sid] = connector
        if ds.refresh_mode == RefreshMode.INTERVAL and ds.enabled:
            self._start_timer(sid, ds.refresh_interval_sec)

    def unregister(self, source_id: str) -> None:
        self._stop_timer(source_id)
        self._connectors.pop(source_id, None)

    def update_connector(self, source_id: str, connector: DataSourceBase) -> None:
        """Replace the connector for an already-registered source (e.g. new viewport bbox)."""
        self._connectors[source_id] = connector

    def refresh_now(self, source_id: str) -> None:
        """Trigger an immediate refresh for *source_id* in a background thread."""
        connector = self._connectors.get(source_id)
        if not connector:
            return
        # Stop any running thread for this source first
        self._stop_thread(source_id)
        self.refresh_started.emit(source_id)

        thread = QThread()
        worker = RefreshWorker(source_id, connector)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        worker.stats.connect(self._on_stats)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        # Remove entry from _threads when the thread finishes to prevent unbounded growth
        thread.finished.connect(lambda _sid=source_id: self._threads.pop(_sid, None))
        self._threads[source_id] = thread
        thread.start()

    # ── Private ────────────────────────────────────────────────────────────────

    def _start_timer(self, source_id: str, interval_sec: int) -> None:
        timer = QTimer(self)
        timer.setInterval(interval_sec * 1000)
        timer.timeout.connect(lambda: self.refresh_now(source_id))
        timer.start()
        self._timers[source_id] = timer

    def _stop_timer(self, source_id: str) -> None:
        timer = self._timers.pop(source_id, None)
        if timer:
            timer.stop()

    def _stop_thread(self, source_id: str) -> None:
        thread = self._threads.pop(source_id, None)
        if thread and thread.isRunning():
            thread.quit()
            thread.wait(2000)

    def shutdown(self) -> None:
        """Stop refresh timers and wait for all active workers before Qt exits."""
        for source_id in list(self._timers):
            self._stop_timer(source_id)
        for source_id in list(self._threads):
            self._stop_thread(source_id)

    def _on_finished(self, source_id: str, rows: list) -> None:
        self.data_refreshed.emit(source_id, rows)

    def _on_stats(self, source_id: str, row_count: int, ms: int) -> None:
        self.refresh_stats.emit(source_id, row_count, ms)

    def _on_error(self, source_id: str, message: str) -> None:
        self.refresh_error.emit(source_id, message)
