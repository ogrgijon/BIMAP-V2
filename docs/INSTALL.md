# BIMAP — Installation & Build Guide

[← Back to README](../readme.md)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Development Install](#2-development-install)
3. [Running the App](#3-running-the-app)
4. [Running Tests](#4-running-tests)
5. [Building a Standalone Executable](#5-building-a-standalone-executable)
6. [CI Pipeline](#6-ci-pipeline)
7. [Security Notes](#7-security-notes)

---

## 1. Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| pip | 23+ recommended |
| Git | Any recent version |
| OS | Windows 10+, macOS 12+, or Linux (Ubuntu 22.04+) |

On **Windows**, install Python from [python.org](https://www.python.org/downloads/) and ensure `python` is on your PATH.

---

## 2. Development Install

```bash
# Clone the repository
git clone https://github.com/ogrgijon/BIMAP-V2.git
cd BIMAP-V2

# Create a virtual environment
python -m venv .venv

# Activate
.venv\Scripts\activate       # Windows (PowerShell)
source .venv/bin/activate    # macOS / Linux

# Install runtime dependencies in editable mode
pip install -e .

# Install dev / test dependencies
pip install -r requirements-dev.txt
```

---

## 3. Running the App

```bash
# Using module entry point (recommended)
python -m bimap.app

# Or, after pip install -e .
bimap
```

On first launch BIMAP creates:
- `~/.bimap/` — application data root
- `~/.bimap/tile_cache/` — cached map tiles
- `~/.bimap/projects/` — default project folder

---

## 4. Running Tests

```bash
# Run full test suite (quiet)
python -m pytest tests/ -q

# Expected: all tests pass

# With coverage report
pip install pytest-cov
python -m pytest tests/ --cov=src/bimap --cov-report=term-missing
```

---

## 5. Building a Standalone Executable

### Portable EXE (recommended — no install required)

```powershell
.\installer\build_installer.ps1 -Version 0.3.0 -PortableOnly
```

Output: `BIMAP-v0.3.0-windows-x64-portable.exe` — double-click to run, no Python needed.

### Onedir build (for Inno Setup installer)

```powershell
pyinstaller installer\bimap.spec `
    --distpath installer\dist `
    --workpath installer\build `
    --noconfirm
# Output folder: installer\dist\BIMAP\
```

Then compile the installer:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\setup.iss
# Output: installer\Output\BIMAP-v0.3.0-setup.exe
```

### Bumping the Version

```bash
python dev/bump_version.py patch
# Updates pyproject.toml and src/bimap/config.py in sync
```

---

## 6. CI Pipeline

GitHub Actions runs on every push and pull request to `main`:

```
.github/workflows/ci.yml
```

Pipeline steps:
1. Checkout
2. Set up Python 3.11
3. `pip install -e . -r requirements-dev.txt`
4. `pytest tests/ -q`
5. On version-tagged push: build portable EXE and create GitHub Release

### Triggering a Release

```bash
git tag v0.3.0
git push origin v0.3.0
```

The workflow automatically builds the EXE, creates a GitHub Release, and attaches the portable binary.

---

## 7. Security Notes

> ⚠️ This section describes known security limitations of the current prototype.

### Plaintext credentials (SEC-005 — MEDIUM)

SQL connection strings and REST API tokens are stored **in plaintext** inside `.bimap` project files (JSON).

- **Do not commit `.bimap` files** containing real credentials to version control.
- Add your project files to `.gitignore` if they reference production databases or APIs.
- For production use, integrate a secret manager (environment variables, `keyring`, Vault) — this is not yet implemented.

### SQL query execution

The SQL connector enforces a `SELECT`-only guard and uses SQLAlchemy `text()` parameterisation. However, the user constructs the query string — treat any query from an untrusted source with appropriate caution.

### Network requests

BIMAP fetches tiles from external providers (OSM, CartoDB, etc.) and geocodes via Nominatim. Your IP is visible to those services. See:
- [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/)
- [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)

### Expression evaluation

Data-binding transform fields use a **safe AST evaluator** — no `eval()`. Only numeric operators and a whitelist of builtins (`str`, `int`, `float`, `round`, `abs`) are permitted.

### General disclaimer

This project is an **experimental research prototype**. It is not production-ready and is provided without warranty. The authors accept no liability for any damages arising from its use.
