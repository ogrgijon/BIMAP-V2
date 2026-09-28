# BIMAP — User Manual

**Version 0.3.0 · March 2026**

> BIMAP is a Python + PyQt6 desktop application for designing presentation-quality PDF maps enriched with business data. It unifies map design, geospatial data integration, and professional export in a single workflow.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Main Window Layout](#2-main-window-layout)
3. [Projects](#3-projects)
4. [Map Navigation](#4-map-navigation)
5. [Drawing Elements](#5-drawing-elements)
6. [Zones](#6-zones)
7. [Keypoints](#7-keypoints)
8. [Annotations](#8-annotations)
9. [Layers Panel](#9-layers-panel)
10. [Properties Panel](#10-properties-panel)
11. [Metadata & Data Binding](#11-metadata--data-binding)
12. [Data Sources](#12-data-sources)
13. [Live Feeds](#13-live-feeds)
14. [Forms & Extensions](#14-forms--extensions)
15. [Style Presets](#15-style-presets)
16. [Keynotes](#16-keynotes)
17. [Measurement Tool](#17-measurement-tool)
18. [Bookmarks](#18-bookmarks)
19. [Delimitation (Administrative Boundaries)](#19-delimitation-administrative-boundaries)
20. [Offline Maps](#20-offline-maps)
21. [Import & Export](#21-import--export)
22. [PDF / Print Composer](#22-pdf--print-composer)
23. [Preferences](#23-preferences)
24. [Keyboard Shortcuts](#24-keyboard-shortcuts)
25. [File Format Reference](#25-file-format-reference)

---

## 1. Getting Started

### Installation

```bash
# Clone repository
git clone https://github.com/ogrgijon/BIMAP-V2.git
cd BIMAP

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -e .
```

### Launching the Application

```bash
python -m bimap.app
```

On first launch, BIMAP creates the following directories in your home folder:

| Path | Purpose |
|------|---------|
| `~/.bimap/` | Application data root |
| `~/.bimap/tile_cache/` | Cached map tiles (max ~512 MB, LRU-evicted) |
| `~/.bimap/projects/` | Default project save location |

### System Requirements

- Python 3.11+
- PyQt6
- Internet connection (for tile downloads and geocoding)
- BIMAP works offline using cached tiles once downloaded

---

## 2. Main Window Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  File  Edit  View  Map  Data  Measurement  Help          Menu Bar   │
├──────────────────────────────────────────────────────────────────────┤
│  [Select][Pan][Polygon][Rect][Circle][Keypoint][Text]…   Tool Bar   │
│  🔍 Search location…  | OSM ▾ | + - | 0° | Grid | Scale  Search   │
├──────────────────────────────────────────────────────────────────────┤
│                    │                           │ Properties ▾        │
│  Layers Panel      │                           │ ┌──────────────────┐│
│  ─────────────     │    Map Canvas             │ │ Style │ Metadata ││
│  ▸ Default         │    (OpenStreetMap tiles   │ └──────────────────┘│
│    ○ Zone A        │     + element overlays)   │                     │
│    📍 Point B      │                           │ Keynotes            │
│    T Annotation    │                           │ ─────────────────── │
│                    │                           │ Data Sources        │
│  [+ Layer]         │                           │ ─────────────────── │
│                    │                           │ Live Feeds          │
├──────────────────────────────────────────────────────────────────────┤
│  Lat: — · Lon: —     Zoom: 14     Sources: 2     🌐 Online          │
└─────────────────────────────────────────────────────────────────────┘
```

### Panels Overview

| Panel | Location | Purpose |
|-------|----------|---------|
| **Tool Bar** | Top row | Switch drawing/editing modes |
| **Search Bar** | Second row | Geocode locations, switch tile provider, zoom |
| **Map Canvas** | Centre | Interactive OSM map with element overlays |
| **Layers Panel** | Left sidebar | Tree view of all elements by layer |
| **Properties** | Right tabs | Edit style and metadata of selected element |
| **Keynotes** | Right tabs | Manage numbered keypoint references |
| **Data Sources** | Right tabs | Manage external data connections |
| **Live Feeds** | Right tabs | Manage real-time position feeds |
| **Status Bar** | Bottom | Current coordinates, zoom, source count, network |

All panels are dockable QDockWidget — they can be moved, floated, or hidden.

---

## 3. Projects

### Creating and Opening

| Action | Menu | Shortcut |
|--------|------|----------|
| New project | File → New Project | Ctrl+N |
| Open project | File → Open… | Ctrl+O |
| Recent projects | File → Recent Projects | — |
| Save | File → Save | Ctrl+S |
| Save As | File → Save As… | Ctrl+Shift+S |

Projects are saved as `.bimap` files (JSON format).

### Auto-Save

BIMAP auto-saves the current project every 5 minutes by default. The interval is configurable in **Preferences → Autosave interval**.

### Backup & Transfer

Use **File → Export Data Backup…** to create a portable `.bimap.zip` that includes the project and all referenced data files — useful for moving projects between workstations.

Restore with **File → Import Data Backup…**.

---

## 4. Map Navigation

### Pan & Zoom

| Action | Result |
|--------|--------|
| Left-click + drag | Pan map |
| Scroll wheel | Zoom in/out (centred on cursor) |
| `+` / `-` keys | Zoom in/out by one level |
| Double-click | Zoom in to that point |
| Search bar `+`/`-` buttons | Zoom controls |

### Tile Provider

Use the **tile provider dropdown** in the search bar to switch between:

- **OSM Standard** — OpenStreetMap default
- **CartoDB Light** — Minimal light-grey basemap
- **CartoDB Dark** — Dark basemap for high contrast overlays
- **OpenTopoMap** — Topographic contour map
- **Custom TMS** — Enter your own tile server URL template

### Location Search

Type an address in the **🔍 Search location…** bar and press Enter. BIMAP geocodes via Nominatim (OpenStreetMap) and pans the map to the result.

Alternatively use **Map → Search Location…** (Ctrl+F) or **Map → Place by Coordinates…** (Ctrl+G) to jump to specific lat/lon coordinates.

### Map Overlays

Toggle these from the search bar or **Preferences**:

- **Grid** — Coordinate grid overlay
- **Scale Bar** — Displays current scale (metric or imperial)
- **North Arrow** — Compass rose indicator
- **Map Rotation** — Enter angle in the rotation spinbox to rotate the canvas view

---

## 5. Drawing Elements

### Tool Modes

Select a tool from the **Tool Bar** or the **Edit** menu:

| Tool | Shortcut | Description |
|------|----------|-------------|
| Select | — | Click to select and move elements |
| Pan | — | Drag to pan the map |
| Draw Polygon Zone | Ctrl+Shift+P | Click vertices; right-click or double-click to close |
| Draw Rectangle Zone | Ctrl+Shift+R | Click and drag to define rectangle |
| Draw Circle Zone | Ctrl+Shift+C | Click centre, drag to set radius |
| Place Keypoint | Ctrl+Shift+K | Click once to drop a pin |
| Place Text Annotation | Ctrl+Shift+T | Click once to place a text box |
| Magic Wand (Lasso) | — | Drag boundary to select multiple zones in bulk |
| Rotate Element | — | Select a rectangle zone, then use ↑/↓ keys or rotation field |
| Measure | M | Click points to measure distances and area |

### Editing Elements

- **Select** — Click element to open it in the Properties panel
- **Move** — Click and drag a selected element to a new position
- **Rotate** (rectangles only) — Select, then press ↑/↓ or type angle in properties
- **Delete** — Select element and press Delete, or right-click → Delete

### Bulk Operations (Lasso)

Activate the **Magic Wand** tool, draw a closed boundary on the canvas. All zones inside the lasso are selected. Right-click to **delete** the selection.

---

## 6. Zones

Zones are coloured geographic areas drawn on the map. They can be polygons, rectangles, or circles.

### Zone Types

| Type | How to Draw | Notes |
|------|-------------|-------|
| **Polygon** | Click vertices; right-click to close | Any freeform shape |
| **Rectangle** | Click and drag | Exact dimensions in metres editable |
| **Circle** | Click centre, drag for radius | Radius editable in metres |

### Zone Properties (Style Tab)

#### Identification

| Field | Description |
|-------|-------------|
| Name | Label shown in Layers panel |
| Group | Category/cluster name |
| Layer | Assign to a named layer |

#### Fill

| Field | Range | Description |
|-------|-------|-------------|
| Color | Hex picker | Fill colour (default `#3388FF`) |
| Opacity | 0–255 | 0 = transparent, 255 = fully opaque |
| Hatch Pattern | None / Horizontal / Vertical / Diagonal / Crosshatch | Pattern overlay |
| SVG Fill | File path | Optional `.svg` rendered as fill graphic |

#### Border

| Field | Range | Description |
|-------|-------|-------------|
| Color | Hex picker | Border colour (default `#1A60CC`) |
| Width | 0–20 px | Border line thickness |
| Style | Solid / Dashed / Dotted | Line style |

#### Label

| Field | Description |
|-------|-------------|
| Text | Label displayed on the zone |
| Font Family | System font |
| Font Size | 6–72 pt |
| Bold / Italic | Style toggles |
| Text Color | Hex picker |
| Background Color | Hex picker (transparent if empty) |
| Offset X / Y | Fine-tune label position in canvas pixels |

#### Geometry

| Field | Applies To | Description |
|-------|-----------|-------------|
| Width (m) | Rectangle | Width in metres |
| Height (m) | Rectangle | Height in metres |
| Radius (m) | Circle | Radius in metres |
| Rotation (°) | Rectangle | Clockwise rotation angle |

> **Note:** Changing Width, Height, or Radius recalculates the zone's geographic coordinates automatically.

---

## 7. Keypoints

Keypoints are pin markers placed at specific geographic coordinates, typically representing locations of interest (warehouses, stores, offices, etc.).

### Placing a Keypoint

1. Select **Place Keypoint** tool (Ctrl+Shift+K)
2. Click on the map at the desired location

Or use **Map → Place by Coordinates…** (Ctrl+G) to enter exact lat/lon values.

### Keypoint Properties

#### Location

| Field | Range | Description |
|-------|-------|-------------|
| Latitude | -90 to +90 | Geographic latitude |
| Longitude | -180 to +180 | Geographic longitude |

#### Appearance

| Field | Options | Description |
|-------|---------|-------------|
| Icon | pin, circle, square, diamond, star, custom path | Marker shape |
| Icon Color | Hex picker | Marker colour (default `#E74C3C`) |
| Icon Size | 8–40 px | Marker size |

#### Info Card

The Info Card is shown when users interact with the keypoint (pop-up details):

| Field | Description |
|-------|-------------|
| Title | Primary label |
| Subtitle | Secondary text |
| Notes | Multi-line free text |
| Image | Path to local image or URL |
| Link URL | Hyperlink (clickable in PDF viewer) |

---

## 8. Annotations

Annotations are non-geographic overlays added on top of the map for presentation purposes.

### Annotation Types

| Type | Description |
|------|-------------|
| **Text Box** | Floating multi-line text area |
| **Callout** | Text with arrow pointing to a geographic coordinate |
| **Legend** | Auto-generated legend block from zone styles |
| **Title Block** | Architectural-style title block (project name, revision, scale, sheet) |
| **Scale Bar** | Map scale indicator |
| **Keynote Table** | Auto-generated table of numbered keypoints |
| **North Arrow** | Compass rose overlay |

### Placing an Annotation

1. Select **Place Text Annotation** tool (Ctrl+Shift+T)
2. Click on the canvas to place it
3. Type content directly in the annotation

### Annotation Properties

| Field | Description |
|-------|-------------|
| Text | Content (multi-line) |
| Font Family / Size | Typography |
| Bold / Italic | Style |
| Text Color | Hex picker |
| Background Color | Hex picker |
| Background Opacity | 0–255 |
| Border Color / Width | Frame style |
| Padding | Internal spacing |
| Anchor Lat/Lon | Pin annotation to a geographic point (for callouts) |

---

## 9. Layers Panel

The Layers panel (left sidebar) organises all elements in a hierarchical tree.

### Structure

```
▸ Sales Regions       ← Layer (expandable)
    ○ Zone A
    ○ Zone B
▸ Logistics           ← Layer
    📍 Warehouse 1
    📍 Warehouse 2
▸ Default             ← Default layer
    T Title Block
```

### Layer Operations

| Action | How |
|--------|-----|
| Create layer | Click **+ Layer** button |
| Rename layer | Double-click layer name |
| Delete layer | Right-click layer → Delete (elements moved to Default) |
| Toggle layer visibility | Checkbox next to layer name |
| Export layer to CSV | Right-click layer → Export Layer CSV… |

### Element Operations

| Action | How |
|--------|-----|
| Select element | Click row (also selects on canvas) |
| Toggle element visibility | Checkbox next to element |
| Lock element | Right-click → Lock (prevents canvas selection/movement) |
| Delete element | Right-click → Delete |
| Move to layer | Drag element row to target layer |

---

## 10. Properties Panel

The Properties panel (right sidebar, **Properties** tab) displays editable fields for the selected element. It has two sub-tabs:

### Style Tab

Shows all visual and geometric properties organised in collapsible sections:

- **Preset** — Apply a saved style preset with one click (if presets exist)
- **Fill** — Color + Opacity slider
- **Border** — Color + Width
- **Label** — Text, font, offsets
- **Geometry** — Width/Height/Radius/Rotation (text inputs with validation)
- **SVG Fill** — Browse local SVG file
- **Form** — Link to a form design and fill form

> All number fields accept direct text input. Press Enter or click away to apply.

### Metadata Tab

Displays a table with columns **Key | Value | 👁 | Source** for the selected element's key-value metadata.

| Column | Description |
|--------|-------------|
| Key | Metadata key name |
| Value | Editable value |
| 👁 | Visibility toggle — hidden keys are excluded from data exports |
| Source | Bound data source (double-click to configure) |

**Adding a row:** Enter key and value in the bottom inputs, click **+ Add**.

**Removing rows:** Select rows, click **Remove Selected**.

**Binding a key to a data source:** Double-click the Source cell → binding dialog opens (see [Metadata & Data Binding](#11-metadata--data-binding)).

---

## 11. Metadata & Data Binding

Each zone, keypoint, and annotation has a free-form key-value metadata store. Values can be static (typed manually) or dynamically sourced from a connected data source.

### Static Metadata

Simply type key and value in the Metadata tab. Example:

| Key | Value |
|-----|-------|
| region | North-West |
| sales_rep | Alice García |
| target | 250000 |

### Binding a Metadata Key to a Data Source

1. Double-click the **Source** cell for a key
2. In the binding dialog:

| Field | Description |
|-------|-------------|
| Data Source | Select configured source (CSV, SQL, API, etc.) |
| Column | Which column from the source to use |
| Filter Field | Source column used to match rows (e.g., `region_name`) |
| Filter Value | Value to match against — use `{{element.name}}` or `{{element.id}}` as dynamic placeholders |
| Aggregate | How to combine matching rows: `first`, `last`, `sum`, `avg`, `count` |

**Example:** To populate a `total_revenue` key for each zone from a CSV where `region_name` matches the zone name:

```
Source:       Sales CSV
Column:       revenue
Filter Field: region_name
Filter Value: {{element.name}}
Aggregate:    sum
```

After a data refresh, `total_revenue` will automatically show the sum of all `revenue` rows where `region_name = <zone name>`.

### Field Mapping (Property-Level Binding)

Data sources can also be bound directly to **element properties** (not just metadata). Configured in the Data Sources panel:

| Field | Example |
|-------|---------|
| Source Column | `highlight_color` |
| Target Property | `style.fill_color` |
| Transform | `str(value)` |

Transform expressions support: arithmetic (`+`, `-`, `*`, `/`, `**`, `//`, `%`), and functions `str()`, `int()`, `float()`, `round()`, `abs()`.

---

## 12. Data Sources

BIMAP can connect to external data to automatically update zone styles and metadata.

### Opening Data Sources Panel

View → Show Data Sources (Ctrl+Shift+D)

### Source Types

#### CSV / Excel

| Setting | Description |
|---------|-------------|
| File Path | Local path to `.csv` or `.xlsx` file |
| Sheet | Sheet name or index (Excel only) |
| Refresh Mode | Manual / On Open / Interval |

#### SQL (PostgreSQL, MySQL, SQLite)

| Setting | Description |
|---------|-------------|
| Connection String | e.g., `postgresql://user:pass@host:5432/dbname` |
| Query | SELECT-only query (write operations are blocked) |

#### REST API (JSON)

| Setting | Description |
|---------|-------------|
| URL | Endpoint URL |
| Data Path | JSONPath to results array (e.g., `results.items`) |
| Auth Token | Optional Bearer token |

#### GeoJSON

| Setting | Description |
|---------|-------------|
| Source | Local file path or HTTPS URL |
| Geometry | Polygon/MultiPolygon → zones; Point → keypoints |

### Refresh Modes

| Mode | Behaviour |
|------|-----------|
| **Manual** | Only refreshes when you click "Refresh Now" |
| **On Open** | Refreshes automatically when the project is loaded |
| **Interval** | Auto-refreshes every N seconds (30–86400 configurable) |

### Managing Sources

Use the **Data Sources panel** buttons:

| Button | Action |
|--------|--------|
| + Add | Create a new data source |
| Edit | Modify settings of selected source |
| Refresh Now | Force immediate refresh |
| Remove | Delete the source |

A status indicator shows: ✓ OK or ✗ Error with the error message.

---

## 13. Live Feeds

Live Feeds display real-time moving positions on the map (vehicles, people, devices, etc.).

### Adding a Live Feed

Data → Live Feeds → add_live_feed…

| Setting | Description |
|---------|-------------|
| Name | Friendly name (e.g., "Fleet Trucks") |
| URL | REST endpoint returning JSON array of positions |
| Lat Field | Name of latitude field in JSON response |
| Lon Field | Name of longitude field in JSON response |
| Label Field | Name of label field (shown next to marker) |
| Speed Field | Optional — field for speed (km/h) |
| Heading Field | Optional — field for bearing (0–360°) |
| Icon | Unicode glyph (●, ▶, ✈, 🚗, 🚲, etc.) |
| Icon Color | Hex picker |
| Poll Interval | Seconds between updates (default 5) |
| Trail Length | Number of historical positions to draw as trail (0 = no trail) |
| Auth Token | Optional Bearer token |

### Feed Presets

BIMAP includes built-in presets for common feeds:

- International Space Station (ISS)
- Commercial Flights (OpenSky Network)
- City Bicycle Sharing (GBFS)
- Madrid BiciMAD

### Feed Status Indicators

| Indicator | Meaning |
|-----------|---------|
| 🟢 Green | Live — recently updated |
| 🟠 Orange | Polling — waiting for next update |
| 🔴 Red | Error — last fetch failed |
| ⚪ Grey | Paused |

### Live Feeds Panel Controls

| Button | Action |
|--------|--------|
| + add_live_feed | Create new feed |
| Edit | Modify selected feed |
| ⏸ Pause / ▶ Resume | Toggle feed on/off |
| Remove | Delete feed |

---

## 14. Forms & Extensions

### Form Designer

**Data → Form Designer…**

Create custom input forms that can be filled in for any zone or keypoint. Filled values are saved directly to the element's metadata.

#### Field Types

| Type | Description |
|------|-------------|
| Text | Single-line text input |
| Number | Numeric input with optional range |
| Dropdown | Select from predefined options |
| Checkbox | Boolean true/false |
| Date | Date picker |
| TextArea | Multi-line text |

#### Creating a Form

1. Open Form Designer
2. Click **+ New Form** and enter a name
3. Add fields with label, type, required flag, and default value
4. Set **Target**: Zone, Keypoint, or Both
5. Save the form

#### Filling a Form

1. Select a zone or keypoint
2. In Properties → Style tab, find the **Form** section
3. Select the form from the dropdown
4. Click **Fill Form…**
5. Enter values in the dialog — the metadata table updates in real-time as you type
6. Click OK to save

### Extensions (HTML5 Viewer Components)

Zones and keypoints can have a custom HTML5/CSS/JavaScript widget attached.

**Use cases:** custom info cards, embedded charts, 3D model viewer, iframes, etc.

#### Managing the Extension Library

**Data → Manage Extensions…**

- Save reusable HTML templates with a name
- Edit or delete library entries

#### Attaching an Extension

1. Select a zone or keypoint
2. In the Metadata tab, click **Set Extension…** / **Edit Extension…**
3. Choose a library template or select *Custom (open editor)*
4. Write or paste HTML in the code editor
5. Click OK to save

#### Viewing an Extension

Click **Open Viewer** in the Metadata tab to open the HTML component in an interactive modal window.

---

## 15. Style Presets

Style presets are named templates that store fill colour, border, opacity, and label font settings. Applying a preset changes all linked visual properties in one click.

### Applying a Preset

1. Select a zone
2. In Properties → Style tab, find the **Preset** dropdown (only visible if presets exist)
3. Select a preset from the list

---

## 16. Keynotes

Keynotes assign sequential reference numbers to keypoints, generating a numbered table suitable for PDF documents.

### Keynotes Panel

Open with **View → Show Keynotes** (Ctrl+Shift+N).

The panel shows:
- **Numbered keypoints** with their assigned number and title
- **Unnumbered keypoints** listed below with `—`

### Assigning a Number

1. Click a keypoint row in the panel (it will also be selected on the canvas)
2. Click **Assign #** to assign the next available number

### Removing a Number

Select 해당 the keypoint and click **Clear #**.

### Keynote Table in PDF

Use an **Annotation → Keynote Table** on the canvas, and the PDF renderer will automatically populate it with all numbered keypoints sorted by their reference number.

---

## 17. Measurement Tool

Measure distances and areas directly on the map.

### Usage

1. Press **M** or use **Measurement → Start Measuring**
2. Click points on the map to build a polyline
3. The overlay shows:
   - Distance from the last point to the current cursor position
   - Cumulative total distance
   - Enclosed area (if the shape forms a closed polygon)
4. Clear with **Measurement → Clear Measurement** (Ctrl+M) or press Esc

> Calculations use the Haversine formula for accurate great-circle distances on the WGS-84 ellipsoid.

---

## 18. Bookmarks

Bookmarks save a named viewport state (map centre, zoom level, rotation) for quick navigation.

### Saving a Bookmark

1. Navigate to the desired view
2. Press **Ctrl+B** or **View → Save Bookmark…**
3. Enter a name

### Loading a Bookmark

**View → Bookmarks → [Bookmark Name]**

---

## 19. Delimitation (Administrative Boundaries)

The delimitation feature fetches an administrative boundary from OpenStreetMap and visualises it on the map to constrain the editing area.

### Setting a Delimitation

1. **Map → Set Delimitation…**
2. Enter a place name (country, region, city, postal code, etc.)
3. BIMAP queries Nominatim and draws the boundary polygon

### Clearing a Delimitation

**Map → Clear Delimitation** removes the boundary display.

---

## 20. Offline Maps

Download tiles for a specific region and zoom range so the map works without an internet connection.

### Downloading Tiles

1. **Map → Offline Map…**
2. Define the bounding box (min/max lat and lon) or use the current viewport
3. Select the zoom level range (e.g., 10–16)
4. Click **Download**

BIMAP stores tiles in `~/.bimap/tile_cache/`. Downloads may take several minutes for large areas or high zoom levels.

When the app detects no internet connection, it automatically uses cached tiles.

---

## 21. Import & Export

### GeoJSON

| Direction | Menu | What it does |
|-----------|------|-------------|
| Import | File → Import GeoJSON… | Polygon → zones; Point → keypoints; properties → metadata |
| Export | File → Export GeoJSON… | All zones and keypoints as GeoJSON FeatureCollection |

### CSV

| Menu | What it does |
|------|-------------|
| File → Export Elements CSV… | All zones + keypoints with attributes (id, name, layer, coordinates, metadata, style) |
| Layers panel → right-click → Export Layer CSV… | Elements of a specific layer only |

### Data Backup

| Direction | Menu | What it does |
|-----------|------|-------------|
| Export | File → Export Data Backup… | Save portable `.bimap.zip` including project and data files |
| Import | File → Import Data Backup… | Restore from `.bimap.zip` or `.bimap` (replaces current project) |

---

## 22. PDF / Print Composer

**File → Print / Export PDF…** (Ctrl+P)

The Map Composer dialog has a live preview on the right and configuration tabs on the left.

### Page & Zoom

| Setting | Options |
|---------|---------|
| Page Size | A4, A3, Letter, Legal |
| Orientation | Portrait / Landscape |
| DPI | 72, 96, 150, 300, 600 |
| Margins | Top, Right, Bottom, Left (mm) |

### Legend

- Per-layer visibility toggle — choose which zone layers appear in the legend
- Custom legend labels override zone names in the printed legend

### Title Block

Architectural-style title block inserted at the bottom or side of the map:

| Field | Description |
|-------|-------------|
| Project Name | Main title |
| Drawn By | Author name |
| Checked By | Reviewer name |
| Revision | Version identifier (e.g., "Rev. 3") |
| Scale | Map scale text (e.g., "1:25 000") |
| Sheet | Sheet identifier (e.g., "1 of 3") |
| Date | Auto-filled with current date or manual entry |

### Info Box

Optional text block with free description, title, and author, placed above or below the map.

### Exporting

- **Export PDF** — Save to `.pdf` file at chosen path
- **Print** — Open system print preview (QPrintPreviewDialog)

---

## 23. Preferences

**Edit → Preferences…** (Ctrl+,)

| Setting | Default | Description |
|---------|---------|-------------|
| Autosave Interval | 300 000 ms (5 min) | How often auto-save runs (0 = disabled) |
| Undo Stack Limit | 0 (unlimited) | Max undo states (0 = unlimited) |
| Default Tile Provider | OSM Standard | Map basemap on new projects |
| Scale Bar | Metric | Metric or Imperial |
| Grid Overlay | Off | Show coordinate grid |
| Network Timeout | 10 s | Seconds before a tile or API request times out |
| Max Markers per Feed | 500 | Cap on live feed marker count |
| Show Error Badge | On | Display feed error badge on markers |
| Language | English | UI language (English / Español) — requires restart |

---

## 24. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New Project |
| Ctrl+O | Open Project |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As… |
| Ctrl+P | Print / Export PDF |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Delete | Delete Selected Element |
| Ctrl+Shift+P | Draw Polygon Zone |
| Ctrl+Shift+R | Draw Rectangle Zone |
| Ctrl+Shift+C | Draw Circle Zone |
| Ctrl+Shift+K | Place Keypoint |
| Ctrl+Shift+T | Place Text Annotation |
| Ctrl+, | Preferences |
| Ctrl+B | Save Bookmark |
| Ctrl+Shift+N | Show Keynotes Panel |
| Ctrl+Shift+D | Show Data Sources Panel |
| Ctrl+F | Search Location |
| Ctrl+G | Place by Coordinates |
| Ctrl+M | Clear Measurement |
| M | Start Measuring |
| + | Zoom In |
| − | Zoom Out |
| ↑ / ↓ | Rotate selected zone ±1° (in Rotate mode) |
| Esc | Cancel current drawing / clear measurement |

---

## 25. File Format Reference

### Project File (`.bimap`)

- **Format:** JSON — Pydantic model serialisation
- **Extension:** `.bimap`
- **Contains:**

| Section | Contents |
|---------|---------|
| `zones` | All zone objects (style, geometry, metadata, bindings) |
| `keypoints` | All keypoint objects (location, icon, info card, metadata) |
| `annotations` | All annotation objects (text, style, position) |
| `layers` | Layer definitions and visibility states |
| `data_sources` | Connection configs (CSV, SQL, REST, GeoJSON) |
| `pdf_layout` | Composer page, title block, legend settings |
| `style_presets` | Named style templates |
| `extension_library` | HTML5 viewer component templates |
| `form_designs` | Custom form definitions |
| `live_layers` | Live feed configurations |
| `map_state` | Last viewport (centre, zoom, rotation, tile provider) |
| `bookmarks` | Saved viewports |

> ⚠️ **Security note:** Project files are plaintext JSON. Do not store database passwords or API tokens in projects shared with untrusted recipients.

### Backup File (`.bimap.zip`)

A ZIP archive containing:
- The `.bimap` project file
- All referenced local files (CSV, Excel, SVG, images)

Designed for transferring complete projects between workstations.

---

## Appendix A — Tips & Workflows

### Typical Data-Driven Map Workflow

1. **New project** (Ctrl+N)
2. **Search or navigate** to your region of interest
3. **Draw zones** representing territories, areas, or locations
4. **Add a data source** (CSV, SQL, or REST) with your business data
5. **Create field mappings** to link data columns to zone colours or metadata
6. **Bind metadata keys** to aggregated data values (e.g., sum of revenue per region)
7. **Label zones** using metadata values in the label text
8. **Add keypoints** for specific locations
9. **Open PDF Composer** and configure page, title block, and legend
10. **Export PDF** for presentations or reports

### Offline Region Map

1. Navigate to the target region
2. **Map → Offline Map…** — download tiles for zoom levels 8–16
3. Disconnect from internet
4. BIMAP continues working with cached tiles

### Sharing a Project

Use **File → Export Data Backup…** to create a `.bimap.zip` that includes the project plus all linked CSV/Excel files. Recipient uses **File → Import Data Backup…** to load it on their machine.

---

*BIMAP is an open-source research prototype. Contributions and bug reports are welcome at [github.com/ogrgijon/BIMAP](https://github.com/ogrgijon/BIMAP).*
