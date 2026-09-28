"""
BIMAP application entry point.

Usage
-----
    python -m bimap.app          # run directly
    bimap                        # if installed via pip/pyproject.toml entry-point
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QSplashScreen

from bimap.config import APP_NAME, APP_ORGANISATION, APP_VERSION, THEME_QSS_PATH

# QWebEngineView requires its module to be imported BEFORE QApplication is created.
# Do it here unconditionally so the viewer dialog works regardless of import order.
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView as _QWebEngineView  # noqa: F401
except ImportError:
    pass  # PyQt6-WebEngine not installed; viewer will fall back to system browser

# Suppress Qt font-directory warnings (harmless on systems without certain fonts)
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false")

# Assets live at the project root (two levels above src/bimap/)
# In a frozen PyInstaller bundle sys._MEIPASS is the extraction directory and
# all datas end up there, so _ROOT points to it directly.
if getattr(sys, "frozen", False):
    _ROOT = Path(sys._MEIPASS)          # type: ignore[attr-defined]
else:
    _ROOT = Path(__file__).parent.parent.parent


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANISATION)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    # Apply VS Code dark theme unless --no-theme is passed
    if "--no-theme" not in sys.argv and THEME_QSS_PATH.exists():
        app.setStyleSheet(THEME_QSS_PATH.read_text(encoding="utf-8"))
    # High-DPI scaling is automatic in Qt 6.x — AA_UseHighDpiPixmaps was removed in Qt 6.7

    # App icon
    _ico = _ROOT / "bimap.ico"
    if _ico.exists():
        app.setWindowIcon(QIcon(str(_ico)))

    # Splash screen — shown before the heavy MainWindow import
    splash: QSplashScreen | None = None
    _splash_png = _ROOT / "bimap_splash.png"
    if _splash_png.exists():
        splash = QSplashScreen(QPixmap(str(_splash_png)))
        splash.show()
        splash.showMessage(
            f"Loading {APP_NAME}…",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#FFFFFF"),
        )
        app.processEvents()

    # Lazy import to keep startup fast and allow QApplication to exist first
    from bimap.ui.main_window import MainWindow

    window = MainWindow()
    app.aboutToQuit.connect(window.shutdown)
    window.show()
    if splash is not None:
        splash.finish(window)
    exit_code = app.exec()
    # Python 3.13 fix: wait for all Qt thread-pool workers to finish before the
    # interpreter tears down the threading module (avoids _DeleteDummyThreadOnDel
    # __del__ TypeError during interpreter shutdown).
    # After waitForDone the Qt threads are idle but their Python "dummy thread"
    # wrappers may not have been GC'd yet.  Force a full GC cycle now, while
    # threading._active_limbo_lock is still valid, so __del__ fires cleanly.
    from PyQt6.QtCore import QThreadPool
    pool = QThreadPool.globalInstance()
    pool.setMaxThreadCount(1)   # stop spawning new threads
    pool.waitForDone(5000)
    pool.setMaxThreadCount(0)   # release all idle threads back to OS

    # Close the tile disk-cache so diskcache's SQLite connections are not
    # closed by the garbage collector after threading has torn down.
    try:
        from bimap.ui.map_canvas.tile_fetcher import get_tile_cache
        get_tile_cache().close()
    except Exception:  # noqa: BLE001
        pass

    import gc as _gc
    _gc.collect()
    _gc.collect()   # two passes: first frees refs, second frees the containers
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
