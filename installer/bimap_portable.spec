# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec — BIMAP portable single-file EXE
# Produces:   installer/dist/BIMAP.exe   (onefile, self-contained)
#
# Build command (from repo root):
#   pyinstaller installer/bimap_portable.spec \
#       --distpath installer/dist --workpath installer/build --noconfirm

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent          # repo root (one level up from installer/)

a = Analysis(
    [str(ROOT / "src" / "bimap" / "app.py")],
    pathex=[str(ROOT / "src")],       # lets PyInstaller resolve 'import bimap'
    binaries=[],
    datas=[
        (str(ROOT / "bimap.ico"),                      "."),
        (str(ROOT / "bimap_splash.png"),               "."),
        (str(ROOT / "src" / "bimap" / "ui" / "dark_theme.qss"), "bimap/ui"),
    ],
    hiddenimports=[
        # PyQt6 extras that the hook may miss
        "PyQt6.sip",
        "PyQt6.QtPrintSupport",
        "PyQt6.QtNetwork",
        "PyQt6.QtSvg",
        # Data / ORM
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.pool",
        "openpyxl",
        "openpyxl.cell._writer",
        # Pydantic v2
        "pydantic",
        "pydantic_core",
        "pydantic.deprecated.decorator",
        # Misc
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
        "reportlab",   # not used -- QPdfWriter handles PDF output
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BIMAP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "bimap.ico"),
    version=None,
)
