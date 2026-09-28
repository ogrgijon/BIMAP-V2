# BIMAP — Architecture

[← Back to README](../readme.md)

---

## Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [Layer Diagram](#2-layer-diagram)
3. [Key Design Decisions](#3-key-design-decisions)
4. [Tech Stack](#4-tech-stack)
5. [Project Structure](#5-project-structure)
6. [Data Flow](#6-data-flow)
7. [Undo / Redo System](#7-undo--redo-system)

---

## 1. High-Level Overview

BIMAP is structured as a classic desktop MVC application with a clear separation between:

- **Domain models** (Pydantic) — the source of truth
- **Engine** — business logic, I/O, rendering
- **UI** (PyQt6) — panels, dialogs, canvas, signals
- **Data layer** — external source connectors and refresh scheduler

All user actions are wrapped in `QUndoCommand` objects so that every mutation is reversible.

---

## 2. Layer Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                        BIMAP Application                       │
├──────────────┬─────────────────┬────────────┬──────────────────┤
│   UI Layer   │   Map Engine    │ Data Layer │  Export Engine   │
│   (PyQt6)    │  (Tiles +       │ (Sources + │ (QPdfWriter /    │
│              │   Overlays)     │  Bindings) │  QPainter)       │
├──────────────┴─────────────────┴────────────┴──────────────────┤
│                       Core Domain Model                        │
│  Project ─┬─ MapState                                          │
│           ├─ Zones[]  ·  Keypoints[]  ·  Annotations[]        │
│           ├─ DataSources[]  ──  FieldMappings[]                │
│           ├─ PDFLayout  ──  LayoutItems[]                      │
│           ├─ StylePresets[]  ·  FormDesigns[]                  │
│           └─ LiveLayers[]  ·  Bookmarks[]                      │
├────────────────────────────────────────────────────────────────┤
│                       Infrastructure                           │
│  Tile Cache · Geocoding · SQLAlchemy · HTTP Client · File I/O  │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **No WebEngine for the map** | OSM tiles rendered directly on a custom `QWidget` via `QPainter` — full overlay control, no 200 MB Chromium dependency |
| 2 | **QPdfWriter instead of ReportLab** | Zero additional dependency; native Qt vector PDF output at any DPI, pixel-perfect |
| 3 | **Command Pattern (QUndoCommand)** | Every user action is a reversible command object — unlimited undo/redo with no extra bookkeeping in application code |
| 4 | **Pydantic domain models** | Domain objects auto-serialise to/from JSON (`.bimap` files) with validation; no hand-written marshalling |
| 5 | **Async tile fetch** | `QThreadPool` workers keep the UI responsive during tile downloads; tiles are LRU-cached on disk |
| 6 | **Safe AST transform eval** | Data-binding `transform` expressions use a whitelist AST evaluator — no `eval()`, no arbitrary code execution |

---

## 4. Tech Stack

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| Language | Python | 3.11+ | Core |
| GUI | PyQt6 | ≥ 6.6 | Desktop UI, map canvas, PDF output |
| PDF | QPdfWriter (Qt built-in) | — | Vector PDF, no extra library |
| Map Tiles | OpenStreetMap / TMS | — | Base map imagery |
| Geocoding | geopy (Nominatim) | — | Address → coordinates |
| Data: SQL | SQLAlchemy | ≥ 2.0 | Database connectivity |
| Data: Excel | openpyxl | ≥ 3.1 | Excel file reading |
| Data: HTTP | requests | — | REST API calls |
| Tile cache | diskcache | ≥ 5.6 | LRU tile & data cache |
| Models | Pydantic | ≥ 2.5 | Validation, JSON serialisation |
| Images | Pillow | ≥ 10.0 | Icon and image manipulation |
| Credentials | keyring | ≥ 24.3 | Secure token storage (planned) |
| Testing | pytest + pytest-qt | — | Unit and integration tests |
| Packaging | PyInstaller | — | Standalone `.exe` / app bundle |

---

## 5. Project Structure

```
BIMAP/
├── readme.md                # Marketing landing page
├── MANUAL.md                # Full user manual
├── pyproject.toml           # Project metadata & entry point
├── requirements.txt         # Runtime dependencies
├── requirements-dev.txt     # Dev / test dependencies
├── dev/
│   ├── bump_version.py      # Sync version across pyproject.toml + config.py
│   └── find_missing_translations.py
├── bimap_splash.png
│
├── docs/
│   ├── ARCHITECTURE.md      # This file
│   ├── INSTALL.md           # Installation, build, CI, security
│   ├── CONTRIBUTING.md      # Contribution guide
│   └── EXTENSIONS.md        # HTML5 extension widget reference
│
├── src/bimap/
│   ├── app.py               # QApplication entry point
│   ├── config.py            # App-wide constants (version, paths)
│   ├── i18n.py              # Internationalisation (EN + ES)
│   │
│   ├── models/              # Pydantic domain models
│   │   ├── project.py       # Root Project model
│   │   ├── map_state.py     # Viewport (centre, zoom, rotation, provider)
│   │   ├── zone.py          # Zone, ZoneStyle, ZoneLabel, MetadataBinding
│   │   ├── keypoint.py      # Keypoint, InfoCard
│   │   ├── annotation.py    # Annotation types
│   │   ├── data_source.py   # DataSource, FieldMapping
│   │   ├── pdf_layout.py    # PDFLayout, TitleBlock, Legend
│   │   └── style.py         # Shared style primitives
│   │
│   ├── ui/
│   │   ├── main_window.py   # MainWindow, menus, toolbar, command wiring
│   │   ├── toolbar.py       # Tool mode buttons
│   │   ├── map_canvas/
│   │   │   ├── tile_widget.py       # OSM tile-fetching QWidget
│   │   │   ├── overlay_renderer.py  # Zones / keypoints / annotations painter
│   │   │   └── interaction.py       # Mouse events, drawing state machine
│   │   ├── panels/
│   │   │   ├── properties_panel.py  # Style + Metadata editor
│   │   │   ├── layers_panel.py      # Layer tree view
│   │   │   ├── keynotes_panel.py    # Keynote list
│   │   │   ├── data_panel.py        # Data sources list
│   │   │   └── live_panel.py        # Live feeds list
│   │   └── dialogs/
│   │       ├── map_composer.py      # PDF composer + preview
│   │       ├── data_source_dialog.py
│   │       ├── form_designer.py
│   │       ├── form_fill_dialog.py
│   │       ├── extension_editor.py
│   │       └── ...
│   │
│   ├── engine/
│   │   ├── commands.py      # All QUndoCommand subclasses
│   │   ├── project_io.py    # .bimap save / load (Pydantic ↔ JSON)
│   │   ├── pdf_renderer.py  # QPdfWriter render pipeline
│   │   ├── tile_math.py     # Lat/lon ↔ tile / pixel coordinate math
│   │   ├── geocoding.py     # Nominatim wrapper
│   │   └── delimitation.py  # Administrative boundary fetcher
│   │
│   └── data/               # Data source connectors
│       ├── base.py          # Abstract base + connector factory
│       ├── csv_source.py
│       ├── sql_source.py
│       ├── api_source.py
│       ├── geojson_source.py
│       └── refresh.py       # Background refresh scheduler
│
├── tests/
│   ├── conftest.py
│   ├── test_models/
│   ├── test_engine/
│   └── test_ui/
│
├── installer/
│   ├── bimap.spec           # PyInstaller spec
│   ├── setup.iss            # Inno Setup installer script
│   └── create_icon.py       # Generate .ico at multiple resolutions
│
└── .github/workflows/
    └── ci.yml               # lint + pytest on push / PR; release on tag
```

---

## 6. Data Flow

```
User edits a property
        │
        ▼
PropertiesPanel.element_changed (signal)
        │
        ▼
MainWindow._apply_property_change()
  ├── _set_nested_attr(element, field, value)
  ├── _update_zone_derived_attrs(element)   ← recalculate coords
  └── EditZoneCommand(old, new, notify_cb)
             │
             ▼
       QUndoStack.push(cmd)
             │
        cmd.redo()
             │
       project.zones[i] = deepcopy(new)
             │
       _notify_canvas()  ──────────────────► canvas.update()
             │                               layers_panel.refresh()
             └──── QTimer(0) ─────────────► props_panel.refresh_current()
                                                   │
                                             _find_in_project(id)
                                                   │
                                             show_element(fresh_zone)
```

---

## 7. Undo / Redo System

All mutations are encapsulated in `_ProjectCommand` subclasses (see `src/bimap/engine/commands.py`):

| Command | Trigger |
|---------|---------|
| `AddZoneCommand` | Draw new zone |
| `RemoveZoneCommand` | Delete zone |
| `EditZoneCommand` | Any property edit, geometry change |
| `AddKeypointCommand` | Place keypoint |
| `EditKeypointCommand` | Property edit |
| `AddAnnotationCommand` | Place annotation |
| `EditAnnotationCommand` | Property edit |
| `SetMetadataCommand` | Add/edit/remove metadata key |
| `EditZoneDragCommand` | Drag-move or rotate zone |

Each command stores deep-copies of the before/after state. `redo()` puts the new state into `project.zones` (or equivalent list); `undo()` reverts to the old state. The `_notify_canvas` callback triggers all dependent UI panels to refresh after each redo/undo.
