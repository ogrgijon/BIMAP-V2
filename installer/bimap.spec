# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec — BIMAP onedir (folder) build
# Produces:   installer/dist/BIMAP/   (folder, suitable for Inno Setup)
#
# Build command (from repo root):
#   pyinstaller installer/bimap.spec \
#       --distpath installer/dist --workpath installer/build --noconfirm

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent          # repo root (one level up from installer/)

a = Analysis(
    [str(ROOT / "src" / "bimap" / "app.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(ROOT / "bimap.ico"),                      "."),
        (str(ROOT / "bimap_splash.png"),               "."),
        (str(ROOT / "src" / "bimap" / "ui" / "dark_theme.qss"), "bimap/ui"),
    ],
    hiddenimports=[
        "PyQt6.sip",
        "PyQt6.QtPrintSupport",
        "PyQt6.QtNetwork",
        "PyQt6.QtSvg",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.pool",
        "openpyxl",
        "openpyxl.cell._writer",
        "pydantic",
        "pydantic_core",
        "pydantic.deprecated.decorator",
        "diskcache",
        "geopy",
        "geopy.geocoders",
        "httpx",
        "keyring",
        "keyring.backends.Windows",
        "keyring.backends.fail",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "xmlrpc",
        "reportlab",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BIMAP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "bimap.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BIMAP",
)
