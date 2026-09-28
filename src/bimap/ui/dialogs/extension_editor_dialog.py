"""HTML5/CSS/JS Extension Editor and Viewer dialog.

Users can write an HTML5 document (with embedded CSS and JS) that will be
rendered in the system browser with the element's data injected as the
``BIMAP_DATA`` JavaScript object.

BIMAP_DATA structure injected at runtime
-----------------------------------------
    {
        "type":     "zone" | "keypoint",
        "id":       "<uuid>",
        "name":     "<element name>",
        "group":    "<group>",
        "layer":    "<layer>",
        "metadata": { "key": "value", ... },
        "attributes": { "key": "value", ... },
        "geometry": { "type": "...", "coordinates": ... },
        // Keypoints only:
        "info_card": {
            "title":    "...",
            "subtitle": "...",
            "notes":    "...",
            "link_url": "...",
            "fields":   [{"label": "...", "value": "..."}, ...]
        }
    }
"""

from __future__ import annotations

import json
import tempfile
import webbrowser
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button

# ── Chart.js bundled asset path ──────────────────────────────────────────────
# chart.min.js is stored alongside the package data for offline use.
# The extension viewer sets a base URL pointing to this directory so that
# templates referencing "chart.min.js" as a relative path load correctly.
_CHARTJS_CDN_URL = "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"
_CHARTJS_LOCAL_SRC = "chart.min.js"   # resolved relative to bimap/data/ at runtime


def _chartjs_script_tag() -> str:
    """Return the <script> tag to load Chart.js — local copy when available, CDN fallback."""
    import importlib.resources
    try:
        # Python 3.9+: files() returns a Traversable
        pkg_data = importlib.resources.files("bimap.data")
        js_path = pkg_data.joinpath(_CHARTJS_LOCAL_SRC)
        if js_path.is_file():
            return f'<script src="{_CHARTJS_LOCAL_SRC}"></script>'
    except Exception:
        pass
    return f'<script src="{_CHARTJS_CDN_URL}"></script>'


# ── Built-in starter templates ───────────────────────────────────────────────

_TEMPLATE_TABLE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>BIMAP Extension</title>
<style>
  body { font-family: sans-serif; background: #1e1e2e; color: #cdd6f4; margin: 0; padding: 16px; }
  h2   { color: #89dceb; margin-bottom: 8px; }
  table{ border-collapse: collapse; width: 100%; }
  th   { background: #313244; color: #cba6f7; text-align: left; padding: 6px 10px; }
  td   { padding: 6px 10px; border-bottom: 1px solid #45475a; }
</style>
</head>
<body>
<h2 id="title"></h2>
<table>
  <thead><tr><th>Key</th><th>Value</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<script>
  const el = BIMAP_DATA;
  document.getElementById('title').textContent = el.name + ' — ' + el.type;
  const tbody = document.getElementById('rows');
  const attributes = el.attributes || el.metadata || {};
  Object.entries(attributes).forEach(([k, v]) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${k}</td><td>${v}</td>`;
    tbody.appendChild(tr);
  });
</script>
</body>
</html>
"""

_TEMPLATE_BAR = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>BIMAP Extension</title>
<style>
  body   { font-family: sans-serif; background: #1e1e2e; color: #cdd6f4; margin: 0; padding: 16px; }
  h2     { color: #89dceb; }
  .bar-wrap { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
  .bar-row  { display: flex; align-items: center; gap: 8px; }
  .bar-label{ width: 140px; font-size: 12px; text-align: right; }
  .bar-bg   { flex: 1; background: #313244; border-radius: 4px; height: 22px; overflow: hidden; }
  .bar-fill { height: 100%; background: #89b4fa; border-radius: 4px;
              display: flex; align-items: center; padding-left: 6px;
              font-size: 11px; white-space: nowrap; transition: width 0.4s; }
</style>
</head>
<body>
<h2 id="title"></h2>
<div class="bar-wrap" id="bars"></div>
<script>
  const el = BIMAP_DATA;
  document.getElementById('title').textContent = el.name;
  const container = document.getElementById('bars');
  const attributes = el.attributes || el.metadata || {};
  const numericEntries = Object.entries(attributes)
    .map(([k, v]) => [k, parseFloat(v)])
    .filter(([, v]) => !isNaN(v));
  const max = Math.max(...numericEntries.map(([, v]) => v), 1);
  numericEntries.forEach(([k, v]) => {
    const pct = (v / max * 100).toFixed(1);
    container.innerHTML += `
      <div class="bar-row">
        <div class="bar-label">${k}</div>
        <div class="bar-bg">
          <div class="bar-fill" style="width:${pct}%">${v}</div>
        </div>
      </div>`;
  });
</script>
</body>
</html>
"""

_TEMPLATE_GAUGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>BIMAP Extension</title>
<style>
  body   { font-family: sans-serif; background: #1e1e2e; color: #cdd6f4; margin: 0;
           display: flex; flex-direction: column; align-items: center; padding: 24px; }
  h2     { color: #89dceb; margin-bottom: 4px; }
  .gauge { position: relative; width: 200px; height: 100px; overflow: hidden; margin: 16px 0; }
  .gauge svg { width: 100%; height: 100%; }
  .value { font-size: 2em; font-weight: bold; color: #a6e3a1; }
  .label { font-size: 0.85em; color: #9399b2; }
</style>
</head>
<body>
<h2 id="name"></h2>
<div class="gauge">
  <svg viewBox="0 0 200 100">
    <path d="M10,100 A90,90 0 0,1 190,100" fill="none" stroke="#313244" stroke-width="18"/>
    <path id="arc" d="M10,100 A90,90 0 0,1 190,100" fill="none"
          stroke="#89b4fa" stroke-width="18" stroke-dasharray="283" stroke-dashoffset="283"/>
  </svg>
</div>
<div class="value" id="val">—</div>
<div class="label" id="key">first numeric metadata key</div>
<script>
  const el = BIMAP_DATA;
  document.getElementById('name').textContent = el.name;
  const attributes = el.attributes || el.metadata || {};
  const entry = Object.entries(attributes)
    .map(([k, v]) => [k, parseFloat(v)])
    .find(([, v]) => !isNaN(v));
  if (entry) {
    const [k, v] = entry;
    document.getElementById('val').textContent = v;
    document.getElementById('key').textContent = k;
    // Assume 0-100 range; clamp
    const pct = Math.min(Math.max(v, 0), 100) / 100;
    document.getElementById('arc').style.strokeDashoffset = (283 * (1 - pct)).toFixed(1);
  }
</script>
</body>
</html>
"""

_TEMPLATE_LINE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>BIMAP Extension</title>
<style>
  body { font-family: sans-serif; background: #1e1e2e; color: #cdd6f4; margin: 0; padding: 16px; }
  h2   { color: #89dceb; margin-bottom: 12px; }
  .chart-wrap { position: relative; height: 240px; }
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
<h2 id="title"></h2>
<div class="chart-wrap"><canvas id="chart"></canvas></div>
<script>
  const el = BIMAP_DATA;
  document.getElementById('title').textContent = el.name;
  const attributes = el.attributes || el.metadata || {};
  const entries = Object.entries(attributes)
    .map(([k, v]) => [k, parseFloat(v)])
    .filter(([, v]) => !isNaN(v));
  new Chart(document.getElementById('chart'), {
    type: 'line',
    data: {
      labels: entries.map(([k]) => k),
      datasets: [{
        label: el.name,
        data: entries.map(([, v]) => v),
        borderColor: '#89b4fa',
        backgroundColor: 'rgba(137,180,250,0.15)',
        pointBackgroundColor: '#cba6f7',
        tension: 0.35,
        fill: true
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#cdd6f4' } } },
      scales: {
        x: { ticks: { color: '#9399b2' }, grid: { color: '#313244' } },
        y: { ticks: { color: '#9399b2' }, grid: { color: '#313244' } }
      }
    }
  });
</script>
</body>
</html>
"""

_TEMPLATE_PIE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>BIMAP Extension</title>
<style>
  body { font-family: sans-serif; background: #1e1e2e; color: #cdd6f4; margin: 0; padding: 16px; }
  h2   { color: #89dceb; margin-bottom: 12px; }
  .chart-wrap { position: relative; height: 260px; }
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
<h2 id="title"></h2>
<div class="chart-wrap"><canvas id="chart"></canvas></div>
<script>
  const el = BIMAP_DATA;
  document.getElementById('title').textContent = el.name;
  const attributes = el.attributes || el.metadata || {};
  const entries = Object.entries(attributes)
    .map(([k, v]) => [k, parseFloat(v)])
    .filter(([, v]) => !isNaN(v));
  const palette = ['#89b4fa','#a6e3a1','#fab387','#f38ba8','#cba6f7','#94e2d5','#f9e2af','#89dceb'];
  new Chart(document.getElementById('chart'), {
    type: 'doughnut',
    data: {
      labels: entries.map(([k]) => k),
      datasets: [{
        data: entries.map(([, v]) => v),
        backgroundColor: palette,
        borderColor: '#1e1e2e',
        borderWidth: 2
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: '#cdd6f4', boxWidth: 14 } }
      }
    }
  });
</script>
</body>
</html>
"""

_TEMPLATE_RADAR = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>BIMAP Extension</title>
<style>
  body { font-family: sans-serif; background: #1e1e2e; color: #cdd6f4; margin: 0; padding: 16px; }
  h2   { color: #89dceb; margin-bottom: 12px; }
  .chart-wrap { position: relative; height: 260px; }
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
<h2 id="title"></h2>
<div class="chart-wrap"><canvas id="chart"></canvas></div>
<script>
  const el = BIMAP_DATA;
  document.getElementById('title').textContent = el.name;
  const attributes = el.attributes || el.metadata || {};
  const entries = Object.entries(attributes)
    .map(([k, v]) => [k, parseFloat(v)])
    .filter(([, v]) => !isNaN(v));
  new Chart(document.getElementById('chart'), {
    type: 'radar',
    data: {
      labels: entries.map(([k]) => k),
      datasets: [{
        label: el.name,
        data: entries.map(([, v]) => v),
        borderColor: '#a6e3a1',
        backgroundColor: 'rgba(166,227,161,0.2)',
        pointBackgroundColor: '#f9e2af',
        pointRadius: 4
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#cdd6f4' } } },
      scales: {
        r: {
          ticks: { color: '#9399b2', backdropColor: 'transparent' },
          grid: { color: '#313244' },
          pointLabels: { color: '#cdd6f4' }
        }
      }
    }
  });
</script>
</body>
</html>
"""

_TEMPLATE_HELLO_WORLD = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {
    margin: 0;
    background: #1e1e2e;
    color: #cdd6f4;
    font-family: Arial, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
  }
  .card {
    background: #313244;
    border-radius: 12px;
    padding: 2rem;
    max-width: 400px;
    text-align: center;
    box-shadow: 0 4px 24px #0006;
  }
  h1 { color: #cba6f7; margin-bottom: 0.5rem; }
  .type { font-size: 0.8rem; letter-spacing: 0.1em; color: #89b4fa; text-transform: uppercase; }
  .meta { font-size: 0.9rem; color: #a6adc8; margin-top: 1rem; }
</style>
</head>
<body>
<script>
// BIMAP_DATA is injected before this document is rendered.
// The fallback keeps the starter useful when opened as a standalone file.
const extensionData = typeof BIMAP_DATA !== "undefined" ? BIMAP_DATA : {
  name: "My Element", type: "zone", attributes: { Example: "value" }
};
</script>
<div class="card">
  <div class="type" id="etype"></div>
  <h1 id="title"></h1>
  <div class="meta" id="meta"></div>
</div>
<script>
  document.getElementById("etype").textContent = extensionData.type || "";
  document.getElementById("title").textContent = extensionData.name || "Hello World";
  const attributes = extensionData.attributes || extensionData.metadata || {};
  const keys = Object.keys(attributes);
  document.getElementById("meta").textContent =
    keys.length ? keys.map(k => k + ": " + attributes[k]).join(" · ") : "No attributes yet.";
</script>
</body>
</html>
"""

_TEMPLATES: dict[str, str] = {
    "Hello World (starter)": _TEMPLATE_HELLO_WORLD,
    "Table (all metadata)": _TEMPLATE_TABLE,
    "Bar Chart (metadata values)": _TEMPLATE_BAR,
    "Gauge (single value)": _TEMPLATE_GAUGE,
    "Line Chart (Chart.js)": _TEMPLATE_LINE,
    "Donut Chart (Chart.js)": _TEMPLATE_PIE,
    "Radar Chart (Chart.js)": _TEMPLATE_RADAR,
}

# Replace CDN Chart.js URL with the appropriate local/CDN script tag in Chart templates
_CHARTJS_SCRIPT_TAG = _chartjs_script_tag()
_CDN_SCRIPT_TAG = f'<script src="{_CHARTJS_CDN_URL}"></script>'
_TEMPLATES = {
    name: html.replace(_CDN_SCRIPT_TAG, _CHARTJS_SCRIPT_TAG)
    for name, html in _TEMPLATES.items()
}


def _build_data_payload(element: Any, etype: str) -> dict:
    """Build the complete, stable BIMAP_DATA object for an extension."""
    all_metadata = dict(getattr(element, "metadata", {}) or {})
    hidden = set(getattr(element, "metadata_hidden", []) or [])

    attributes: dict[str, Any] = dict(all_metadata)
    for field in (
        "zone_type", "radius_m", "width_m", "height_m", "rotation_deg",
        "lat", "lon", "icon", "icon_color", "icon_size", "keynote_number",
    ):
        if hasattr(element, field):
            value = getattr(element, field)
            attributes[field] = value.value if hasattr(value, "value") else value

    payload: dict[str, Any] = {
        "type": etype,
        "id": str(getattr(element, "id", "")),
        "name": getattr(element, "name", "") or "",
        "group": getattr(element, "group", "") or "",
        "layer": getattr(element, "layer", "") or "",
        "metadata": {k: v for k, v in all_metadata.items() if k not in hidden},
        "attributes": attributes,
    }

    coordinates = getattr(element, "coordinates", None) or []
    if coordinates:
        geometry: dict[str, Any] = {
            "type": "polygon",
            "coordinates": [
                {"lat": point.lat, "lon": point.lon} for point in coordinates
            ],
        }
        zone_type = getattr(element, "zone_type", None)
        if zone_type is not None:
            geometry["type"] = (
                zone_type.value if hasattr(zone_type, "value") else str(zone_type)
            )
        payload["geometry"] = geometry
    elif hasattr(element, "lat") and hasattr(element, "lon"):
        payload["geometry"] = {
            "type": "point",
            "coordinates": {
                "lat": getattr(element, "lat", 0.0),
                "lon": getattr(element, "lon", 0.0),
            },
        }

    if etype == "keypoint":
        info_card = getattr(element, "info_card", None)
        if info_card is not None:
            payload["info_card"] = {
                "title": getattr(info_card, "title", "") or "",
                "subtitle": getattr(info_card, "subtitle", "") or "",
                "notes": getattr(info_card, "notes", "") or "",
                "link_url": getattr(info_card, "link_url", "") or "",
                "fields": [
                    {"label": field.label, "value": field.value}
                    for field in getattr(info_card, "fields", [])
                ],
            }

    return payload


def launch_extension_in_browser(element: Any, etype: str) -> None:
    """Inject BIMAP_DATA into the element's extension_html and open in the
    system default browser via a temporary file.

    Raises ``ValueError`` if the element has no extension_html set.
    """
    html_template: str = getattr(element, "extension_html", "").strip()
    if not html_template:
        raise ValueError("No extension configured for this element.")

    payload = _build_data_payload(element, etype)
    data_js = json.dumps(payload, ensure_ascii=False, indent=2)
    injection = f"<script>\nconst BIMAP_DATA = {data_js};\n</script>\n"

    # Inject the data block right before </head> or if not found, at the top.
    if "</head>" in html_template:
        rendered = html_template.replace("</head>", injection + "</head>", 1)
    else:
        rendered = injection + html_template

    tmp = tempfile.NamedTemporaryFile(
        suffix=".html", mode="w", encoding="utf-8", delete=False
    )
    tmp.write(rendered)
    tmp.close()
    webbrowser.open(Path(tmp.name).as_uri())


class ExtensionEditorDialog(QDialog):
    """Full-screen HTML5/CSS/JS editor for a single element's extension.

    After ``exec()`` returns ``Accepted``, read ``html_result`` to get the
    saved HTML template (empty str means "clear the extension").
    """

    def __init__(
        self,
        element: Any,
        etype: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._element = element
        self._etype = etype
        name = getattr(element, "name", str(getattr(element, "id", "")))
        self.setWindowTitle(
            t("Extension Editor") + f" — {name}"
        )
        self.resize(800, 640)
        self.html_result: str = getattr(element, "extension_html", "")
        self._setup_ui()
        self._show_onboarding()

    def _show_onboarding(self) -> None:
        """Show a first-use explanation of BIMAP extensions (once per install)."""
        s = QSettings("BIMAP", "BIMAP")
        if s.value("extension_editor_intro_shown", False, type=bool):
            return
        s.setValue("extension_editor_intro_shown", True)
        QMessageBox.information(
            self,
            "BIMAP Extensions",
            "<b>BIMAP Extensions</b> are HTML5 pages embedded in a zone or keypoint.<br><br>"
            "At runtime they receive a <code>BIMAP_DATA</code> JavaScript object containing:<br>"
            "&nbsp;&bull;&nbsp;<b>type</b> — <i>'zone'</i> or <i>'keypoint'</i><br>"
            "&nbsp;&bull;&nbsp;<b>name</b> — element name<br>"
            "&nbsp;&bull;&nbsp;<b>metadata</b> — dict of key→value pairs you defined<br>"
            "&nbsp;&bull;&nbsp;<b>info_card</b> — title, body, tags (keypoints only)<br><br>"
            "Use the <i>Load Template</i> dropdown to start from a built-in example, or "
            "<i>From Library…</i> to import a saved template from your extension library.",
        )

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Header / template loader ──────────────────────────────────────── #
        top_row = QHBoxLayout()
        hint = QLabel(
            "Write an HTML5 document. "
            "<code>BIMAP_DATA</code> is injected as a JS variable with element "
            "data (name, type, metadata, info_card for keypoints)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #858585; font-size: 11px;")
        top_row.addWidget(hint, 1)

        tpl_combo = QComboBox()
        tpl_combo.addItem(t("Load Template"))
        for name in _TEMPLATES:
            tpl_combo.addItem(t(name))
        tpl_combo.currentTextChanged.connect(self._on_template_selected)
        top_row.addWidget(tpl_combo)

        btn_from_lib = QPushButton(t("From Library\u2026"))
        btn_from_lib.setToolTip(t("Import HTML from a saved extension library template"))
        btn_from_lib.clicked.connect(self._from_library)
        top_row.addWidget(btn_from_lib)

        btn_reference = QPushButton(t("Data Reference"))
        btn_reference.setToolTip(t("Show BIMAP_DATA fields and JavaScript examples"))
        btn_reference.clicked.connect(self._show_data_reference)
        top_row.addWidget(btn_reference)

        root.addLayout(top_row)

        # ── Code editor ───────────────────────────────────────────────────── #
        self._editor = QPlainTextEdit()
        self._editor.setPlainText(self.html_result)
        mono = QFont("Consolas", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._editor.setFont(mono)
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._editor.setStyleSheet(
            "background: #1e1e1e; color: #d4d4d4;"
            "border: 1px solid #3C3C3C;"
        )
        self._editor.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._editor, 1)

        # ── Bottom bar ────────────────────────────────────────────────────── #
        btn_row = QHBoxLayout()
        btn_preview = QPushButton(t("Open in Browser"))
        btn_preview.setToolTip(t("Inject current data and open in the system browser"))
        btn_preview.clicked.connect(self._preview)
        btn_row.addWidget(btn_preview)
        btn_row.addStretch()

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        add_dialog_help_button(btn_box, self, "Extension Editor window help")
        btn_row.addWidget(btn_box)
        root.addLayout(btn_row)

    def _show_data_reference(self) -> None:
        """Show the runtime BIMAP_DATA contract and copyable examples."""
        dialog = QDialog(self)
        dialog.setWindowTitle(t("BIMAP_DATA Reference"))
        dialog.resize(700, 560)
        layout = QVBoxLayout(dialog)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(
          f"""
          <h2>BIMAP_DATA</h2>
          <p>{t("The extension receives the selected zone or keypoint as the global JavaScript object BIMAP_DATA.")}</p>
          <h3>{t("Available fields")}</h3>
          <table cellpadding="5" cellspacing="0" border="1">
            <tr><th>{t("JavaScript")}</th><th>{t("Contents")}</th></tr>
            <tr><td><code>BIMAP_DATA.type</code></td><td><code>zone</code> {t("or")} <code>keypoint</code></td></tr>
            <tr><td><code>BIMAP_DATA.id</code></td><td>{t("Object UUID")}</td></tr>
            <tr><td><code>BIMAP_DATA.name</code></td><td>{t("Object name")}</td></tr>
            <tr><td><code>BIMAP_DATA.group</code></td><td>{t("Object group")}</td></tr>
            <tr><td><code>BIMAP_DATA.layer</code></td><td>{t("Map layer")}</td></tr>
            <tr><td><code>BIMAP_DATA.metadata</code></td><td>{t("Visible custom metadata")}</td></tr>
            <tr><td><code>BIMAP_DATA.attributes</code></td><td>{t("All metadata and object attributes")}</td></tr>
            <tr><td><code>BIMAP_DATA.geometry</code></td><td>{t("Geometry type and coordinates")}</td></tr>
            <tr><td><code>BIMAP_DATA.info_card</code></td><td>{t("Keypoint information card")}</td></tr>
          </table>
          <h3>{t("Common object attributes")}</h3>
          <p><code>zone_type</code>, <code>width_m</code>, <code>height_m</code>,
          <code>radius_m</code>, <code>rotation_deg</code>, <code>lat</code>,
          <code>lon</code>, <code>icon</code>, <code>icon_color</code>,
          <code>icon_size</code>, {t("and")} <code>keynote_number</code>.</p>
          <h3>{t("JavaScript examples")}</h3>
          <pre>const data = BIMAP_DATA;

    title.textContent = data.name;
    const status = data.metadata.status || "Unknown";
    const width = Number(data.attributes.width_m || 0);
    const height = Number(data.attributes.height_m || 0);
    const points = data.geometry?.coordinates || [];
    const notes = data.info_card?.notes || "";</pre>
          <p><b>{t("Tip")}</b>: {t("Use attributes for dimensions, hidden derived values, and object defaults.")}</p>
          """
        )
        layout.addWidget(browser, 1)

        actions = QHBoxLayout()
        copy_button = QPushButton(t("Copy JavaScript Example"))
        copy_button.clicked.connect(
          lambda: QApplication.clipboard().setText(
            "const data = BIMAP_DATA;\n"
            "const width = Number(data.attributes.width_m || 0);\n"
            "const height = Number(data.attributes.height_m || 0);\n"
            "const status = data.metadata.status || \"Unknown\";"
          )
        )
        actions.addWidget(copy_button)
        actions.addStretch()
        close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button.rejected.connect(dialog.reject)
        actions.addWidget(close_button)
        layout.addLayout(actions)
        dialog.exec()

    # ── Slots ──────────────────────────────────────────────────────────────── #

    def _from_library(self) -> None:
        """Show a picker to load HTML from the project extension library."""
        library = []
        # Traverse up to find a parent widget that has _project (main window)
        w = self.parent()
        while w is not None:
            library = getattr(getattr(w, "_project", None), "extension_library", [])
            if library:
                break
            w = w.parent() if hasattr(w, "parent") else None
        if not library:
            QMessageBox.information(
                self,
                t("Extension Library"),
                "No templates saved in the extension library yet.\n"
                "Use Data \u2192 Manage Extensions\u2026 to create library entries.",
            )
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(t("Choose from Library"))
        dlg.resize(420, 300)
        vl = QVBoxLayout(dlg)
        vl.addWidget(QLabel(t("Select a template to load into the editor:")))
        lst = QListWidget()
        for tpl in library:
            lst.addItem(tpl.name)
        vl.addWidget(lst)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        vl.addWidget(btns)
        if dlg.exec() and lst.currentRow() >= 0:
            tpl = library[lst.currentRow()]
            if not self._editor.toPlainText().strip() or QMessageBox.question(
                self,
                t("Load Template"),
                "Replace current content with the selected template?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                self._editor.setPlainText(tpl.html)

    def _on_template_selected(self, text: str) -> None:
        key = text
        # Reverse-translate if in ES
        for en_key, tpl in _TEMPLATES.items():
            if t(en_key) == text or en_key == text:
                if not self._editor.toPlainText().strip() or QMessageBox.question(
                    self,
                    "Load Template",
                    "Replace current content with the selected template?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                ) == QMessageBox.StandardButton.Yes:
                    self._editor.setPlainText(tpl)
                break

    def _preview(self) -> None:
        html = self._editor.toPlainText().strip()
        if not html:
            QMessageBox.warning(self, "Preview", t("HTML content is required."))
            return
        payload = _build_data_payload(self._element, self._etype)
        data_js = __import__("json").dumps(payload, ensure_ascii=False, indent=2)
        injection = f"<script>\nconst BIMAP_DATA = {data_js};\n</script>\n"
        if "</head>" in html:
            rendered = html.replace("</head>", injection + "</head>", 1)
        else:
            rendered = injection + html
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            suffix=".html", mode="w", encoding="utf-8", delete=False
        )
        tmp.write(rendered)
        tmp.close()
        import webbrowser
        from pathlib import Path
        webbrowser.open(Path(tmp.name).as_uri())

    def _on_save(self) -> None:
        self.html_result = self._editor.toPlainText().strip()
        self.accept()
