# BIMAP Extensions Manual

Extensions let you attach a custom **HTML5 / CSS / JavaScript widget** to any zone or keypoint on the map. When the viewer opens, BIMAP automatically injects the element's live data as a JavaScript object called `BIMAP_DATA`, so your template can render charts, tables, gauges, sensor readings, or any other display without any server-side code.

---

## Table of Contents

1. [What is an Extension?](#1-what-is-an-extension)
2. [BIMAP_DATA Reference](#2-bimap_data-reference)
3. [Creating an Extension](#3-creating-an-extension)
4. [The Extension Library](#4-the-extension-library)
5. [Opening the Viewer](#5-opening-the-viewer)
6. [Built-in Templates](#6-built-in-templates)
7. [Example: Water Quality Monitoring Widget](#7-example-water-quality-monitoring-widget)
8. [Tips and Gotchas](#8-tips-and-gotchas)

---

## 1. What is an Extension?

An extension is a self-contained HTML document assigned to a map element. It can be as simple as a styled metadata table or as complex as a real-time chart powered by a public API.

Key facts:

- Stored **inside the `.bimap` project file** — no external files needed.
- Rendered **inside BIMAP** using an embedded browser (requires `PyQtWebEngine`) or in your system browser as a fallback.
- The `BIMAP_DATA` variable is injected at render time, so the template always reflects the current state of the element.
- The Extension Library lets you save and reuse templates across many elements.

---

## 2. BIMAP_DATA Reference

When BIMAP renders an extension it prepends a `<script>` block containing:

```js
const BIMAP_DATA = { ... };
```

### Common fields (all element types)

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `"zone"` or `"keypoint"` |
| `id` | `string` | UUID of the element |
| `name` | `string` | Element name |
| `group` | `string` | Group label (may be empty) |
| `layer` | `string` | Layer name (may be empty) |
| `metadata` | `object` | Key/value pairs from the Metadata tab |

### Keypoint-only fields

When `type === "keypoint"` and the element has an Info Card configured, the object also includes:

```js
BIMAP_DATA.info_card = {
  title:    "Point Title",
  subtitle: "Subtitle text",
  notes:    "Free-form notes",
  link_url: "https://example.com",
  fields: [
    { label: "Field A", value: "123" },
    { label: "Field B", value: "456" }
  ]
}
```

### Minimal example

```js
const el = BIMAP_DATA;
console.log(el.name);               // "Station A"
console.log(el.metadata["pH"]);     // "7.4"
console.log(el.info_card?.title);   // "Station A — River Monitoring"
```

---

## 3. Creating an Extension

1. Select a zone or keypoint on the map.
2. Open the **Properties panel** (right-click → Properties, or the panel on the right).
3. Click the **Extension** tab.
4. Click **Create Extension…** (or **Edit Extension…** if one already exists).
5. The Extension Editor opens with:
   - A **template picker** (Table, Bar Chart, Gauge, or blank).
   - A **HTML editor** on the left.
   - A **live preview** on the right that re-renders as you type.
6. Edit the HTML, then click **Save**.

The extension HTML is saved into the element and persisted in the `.bimap` project file.

---

## 4. The Extension Library

The library stores reusable templates at the project level. Any zone or keypoint can then adopt a library template in one click.

### Managing the library

Go to **Data → Manage Extensions…** to open the Extension Library Manager.

- **New** — creates a blank entry.
- **Delete** — removes the selected entry (does not affect elements that already use that HTML).
- **Name / Description** — edit the fields on the right.
- **HTML** — paste or write the template code.
- Click **OK** to save changes back to the project.

### Applying a library template to an element

1. Select the element and open its Properties panel → **Extension** tab.
2. Click **From Library…**.
3. Pick a template from the list and click **OK**.
4. The template HTML is copied into the element's extension field. You can then edit it further via **Edit Extension…**.

> **Tip:** "From Library" copies the template — editing the element's extension afterwards does **not** change the library entry.

---

## 5. Opening the Viewer

There are three ways to open the rendered extension for an element:

| Method | How |
|--------|-----|
| **Launch Viewer** button | Properties panel → Extension tab → *Launch Viewer* |
| **Right-click context menu** | Right-click an element on the map → *🔗 Open Extension…* (only appears if an extension is set) |
| **System browser** | If `PyQtWebEngine` is not installed, BIMAP falls back to opening a temp HTML file in your default browser |

The in-app viewer:

- Opens as a **floating, resizable window** that stays on top of the map.
- Has a **Reload** button to re-inject fresh `BIMAP_DATA` after you edit the element's metadata.
- Can also be **opened in your browser** using the *Open in Browser* button.

---

## 6. Built-in Templates

The editor provides three starter templates accessible via the *Insert Template* menu.

### Table — all metadata

Renders every metadata key/value pair in a clean dark table.

```
Name: Station A  |  Type: zone
── Key ──────── Value ──
pH              7.4
Temperature     21°C
Turbidity       3.2 NTU
```

### Bar Chart — metadata values

Reads all metadata fields that parse as numbers and draws horizontal bars, scaled to the maximum value.

### Gauge — single value

Reads the first numeric metadata field and renders a semicircular gauge (0–100 range assumed; values are clamped).

---

## 7. Example: Water Quality Monitoring Widget

Below is a complete extension template that compares multiple sensor readings against safe thresholds and colors each bar accordingly (green = safe, red = alert).

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Water Quality</title>
<style>
  body {
    font-family: sans-serif;
    background: #1e1e2e;
    color: #cdd6f4;
    margin: 0;
    padding: 20px;
  }
  h2   { color: #89dceb; margin-bottom: 4px; }
  .sub { color: #9399b2; font-size: 0.85em; margin-bottom: 16px; }
  .row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .lbl { width: 130px; font-size: 13px; text-align: right; }
  .bg  { flex: 1; background: #313244; border-radius: 4px; height: 24px; overflow: hidden; }
  .bar { height: 100%; border-radius: 4px;
         display: flex; align-items: center; padding-left: 8px;
         font-size: 12px; transition: width 0.4s; }
  .safe  { background: #a6e3a1; color: #1e1e2e; }
  .alert { background: #f38ba8; color: #1e1e2e; }
</style>
</head>
<body>
<h2 id="name"></h2>
<div class="sub" id="subtitle"></div>

<div id="bars"></div>

<script>
  // ── Thresholds (key → max safe value) ─────────────────────────────── //
  const THRESHOLDS = {
    "pH":          8.5,
    "Temperature": 25,
    "Turbidity":   5,
    "Nitrates":    50,
    "Conductivity": 1500,
  };

  const el = BIMAP_DATA;
  document.getElementById('name').textContent = el.name;
  if (el.info_card) {
    document.getElementById('subtitle').textContent = el.info_card.subtitle || '';
  }

  const container = document.getElementById('bars');
  const numericEntries = Object.entries(el.metadata)
    .map(([k, v]) => [k, parseFloat(v)])
    .filter(([, v]) => !isNaN(v));

  const maxVal = Math.max(...numericEntries.map(([, v]) => v), 1);

  numericEntries.forEach(([k, v]) => {
    const threshold  = THRESHOLDS[k] ?? maxVal;
    const isSafe     = v <= threshold;
    const pct        = Math.min((v / Math.max(threshold, maxVal)) * 100, 100).toFixed(1);
    const cls        = isSafe ? 'safe' : 'alert';

    container.innerHTML += `
      <div class="row">
        <div class="lbl">${k}</div>
        <div class="bg">
          <div class="bar ${cls}" style="width:${pct}%">${v}</div>
        </div>
      </div>`;
  });
</script>
</body>
</html>
```

**How to use it:**

1. Add sensor readings as metadata on the zone (e.g., `pH = 7.4`, `Temperature = 21`).
2. Paste the template into the Extension Editor and click **Save**.
3. Open the viewer — each parameter is shown as a bar, colored green (safe) or red (alert).
4. Adjust the `THRESHOLDS` object to match your local regulatory limits.

---

## 8. Tips and Gotchas

- **Same-origin restrictions**: The in-app viewer uses a local URL (the HTML is written to a temp file); external `fetch()` calls to HTTP APIs work only when the Chromium sandbox allows them. If you need to pull live data, prefer `https://` API endpoints — most public APIs support CORS.
- **No persistence in the template**: `BIMAP_DATA` is re-injected fresh each time you open the viewer. If your extension writes to `localStorage`, that state survives between viewer opens but is not stored in the `.bimap` file.
- **Library vs. element copy**: "From Library…" copies the HTML at the moment of import. Later changes to the library entry are **not** reflected in elements that already imported it (and vice versa).
- **Fallback mode (no PyQtWebEngine)**: When the embedded browser is unavailable, BIMAP writes the rendered HTML to a temporary file and opens it in your system browser. The temp file is deleted when the dialog closes.
- **Fonts and images**: You can reference fonts via CDN (`fonts.googleapis.com`) or embed them as Base64 `data:` URIs. External `<img src="...">` tags work as long as the URL is reachable.
- **Chart libraries**: CDN-hosted libraries like [Chart.js](https://www.chartjs.org/) or [Plotly](https://plotly.com/javascript/) work out of the box:
  ```html
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  ```
