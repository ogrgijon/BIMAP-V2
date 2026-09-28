<div align="center">

# BIMAP
### Business Intelligence Map Designer

**Turn your data into presentation-quality PDF maps — no GIS expertise required.**

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Tests](https://img.shields.io/badge/tests-39%20passed-brightgreen)

[Get Started](#-quick-start) · [User Manual](MANUAL.md) · [Architecture](docs/ARCHITECTURE.md) · [Extensions](docs/EXTENSIONS.md)

<br/>

![BIMAP Screenshot](bimap_splash.png)

</div>

---

## What is BIMAP?

BIMAP is a **Python desktop application** that lets analysts, consultants, and operations teams design data-driven maps and export them as polished PDF documents — all without touching a GIS tool or a web service.

Draw territories. Connect your data. Export a PDF. Done.

---

## Who is it for?

| Role | How they use it |
|------|----------------|
| **Business Analyst** | Sales territory maps, market-penetration heat zones |
| **Consultant** | Client-facing maps with KPI overlays and branded title blocks |
| **Operations Manager** | Logistics routes, warehouse coverage, fleet tracking |
| **Real Estate** | Property portfolios and zoning overlays |
| **Marketing** | Campaign reach maps and demographic zones |

---

## Key Features

### 🗺️ Interactive Map Canvas
Draw directly on OpenStreetMap tiles. Switch between providers (OSM, CartoDB Light/Dark, OpenTopoMap, custom TMS). Search any address and jump to it instantly.

### 📐 Rich Drawing Tools
- **Zones** — polygon, rectangle (width × height in metres), circle (radius in metres)
- **Keypoints** — pins with info cards, images, and hyperlinks
- **Annotations** — text boxes, callouts, north arrows, scale bars, title blocks, keynote tables
- **Lasso select** to bulk-manage multiple elements at once

### 📊 Live Data Integration
Connect zones and keypoints to your data and have them auto-update:
- **CSV / Excel** — local files, auto-reload on change
- **SQL** — PostgreSQL, MySQL, SQLite (SELECT-only)
- **REST API** — JSON endpoints with JSONPath field mapping
- **GeoJSON** — local file or HTTPS URL

### 📡 Real-Time Feeds
Track moving assets on the map with live REST feeds. Configurable icons, trail history, and polling interval. Built-in presets for ISS, commercial flights, city bikes, and more.

### 📄 Professional PDF Export
Full-featured **Map Composer** with WYSIWYG live preview:
- A4 / A3 / Letter / Legal, portrait or landscape
- DPI 72 – 600
- Architectural title block (project, revision, scale, sheet)
- Auto-generated legend and keynote table
- Send to printer or export `.pdf`

### 🔁 Unlimited Undo / Redo
Every action — draw, edit, delete, data refresh — is a reversible command. Nothing is ever one click away from disaster.

### 🌐 Offline Support
Download tile caches for any region and zoom range. The app works fully offline using cached tiles.

---

## ⚡ Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/ogrgijon/BIMAP-V2.git
cd BIMAP-V2

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS / Linux

# 3. Install
pip install -e .

# 4. Launch
python -m bimap.app
```

→ Full installation guide, packaging, and CI setup: [docs/INSTALL.md](docs/INSTALL.md)

---

## 📘 Documentation

| Document | Description |
|----------|-------------|
| [MANUAL.md](MANUAL.md) | Complete user manual — all features, panels, shortcuts |
| [docs/EXTENSIONS.md](docs/EXTENSIONS.md) | HTML5 widget extensions — `BIMAP_DATA` reference and templates |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture, tech stack, project structure, design decisions |
| [docs/INSTALL.md](docs/INSTALL.md) | Detailed installation, building EXE, and CI pipeline |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | How to contribute, code style, PR workflow |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| GUI | PyQt6 ≥ 6.6 |
| PDF output | QPdfWriter (built-in Qt — no extra library) |
| Map tiles | OpenStreetMap / any TMS |
| Geocoding | geopy (Nominatim) |
| SQL | SQLAlchemy ≥ 2.0 |
| Models | Pydantic ≥ 2.5 |
| Packaging | PyInstaller |

→ Full stack details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## ⚠️ Disclaimer

This project is an **experimental research prototype**, shared for learning and collaboration.  
It is **not production-ready** and carries no warranty.  
Do not store production credentials in `.bimap` project files.

See [docs/INSTALL.md](docs/INSTALL.md#security-notes) for the full security note.

---

## 📄 License

MIT License — see [LICENSE](LICENSE).  
Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) — [ODbL](https://opendatacommons.org/licenses/odbl/).

