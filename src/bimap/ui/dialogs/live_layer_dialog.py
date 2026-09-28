"""LiveLayerDialog — two-tab dialog for creating/editing a LiveLayer feed."""

from __future__ import annotations

import json
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button
from bimap.ui.widgets import ColorButton as _ColorButton
from bimap.models.live_layer import LiveLayer


# ── Icon gallery ───────────────────────────────────────────────────────────────

#: (glyph, display-label) pairs shown in the icon picker combo.
_ICON_GALLERY: list[tuple[str, str]] = [
    ("●",  "● Dot"),
    ("▶",  "▶ Arrow"),
    ("✈",  "✈ Aircraft"),
    ("🚁", "🚁 Helicopter"),
    ("🚀", "🚀 Rocket"),
    ("🛸", "🛸 UFO/Satellite"),
    ("🚢", "🚢 Ship"),
    ("⛵", "⛵ Sailboat"),
    ("⚓", "⚓ Anchor"),
    ("🚌", "🚌 Bus"),
    ("🚎", "🚎 Trolleybus"),
    ("🚂", "🚂 Train"),
    ("🚇", "🚇 Metro"),
    ("🚗", "🚗 Car"),
    ("🏍", "🏍 Motorcycle"),
    ("🚲", "🚲 Bicycle"),
    ("🛴", "🛴 Scooter"),
    ("🚶", "🚶 Person"),
    ("📍", "📍 Pin"),
    ("★",  "★ Star"),
    ("◆",  "◆ Diamond"),
    ("⬡",  "⬡ Hexagon"),
]


# ── Free feed presets ──────────────────────────────────────────────────────────

@dataclass
class _Preset:
    name: str
    url: str
    lat_field: str
    lon_field: str
    label_field: str
    poll_ms: int
    icon: str
    icon_color: str
    auth_header: str = ""
    note: str = ""


_PRESETS: list[_Preset] = [
    _Preset(
        name="ISS — International Space Station",
        url="https://api.wheretheiss.at/v1/satellites/25544",
        lat_field="latitude",
        lon_field="longitude",
        label_field="name",
        poll_ms=5000,
        icon="🛸",
        icon_color="#00e5ff",
        note="",
    ),
    _Preset(
        name="OpenSky — Flights over Europe (free tier)",
        url="https://opensky-network.org/api/states/all?lamin=36&lomin=-10&lamax=55&lomax=25",
        lat_field="lat",
        lon_field="lon",
        label_field="callsign",
        poll_ms=12000,
        icon="✈",
        icon_color="#ffcc00",
        note="Rate-limited; anonymous tier allows ~1 req/10 s.",
    ),
    _Preset(
        name="Oslo City Bikes — station info (GBFS)",
        url="https://gbfs.urbansharing.com/oslobysykkel.no/station_information.json",
        lat_field="lat",
        lon_field="lon",
        label_field="name",
        poll_ms=60000,
        icon="🚲",
        icon_color="#22c55e",
    ),
    _Preset(
        name="NYC Citi Bike — station info (GBFS)",
        url="https://gbfs.citibikenyc.com/gbfs/en/station_information.json",
        lat_field="lat",
        lon_field="lon",
        label_field="name",
        poll_ms=60000,
        icon="🚲",
        icon_color="#0ea5e9",
    ),
    _Preset(
        name="Madrid BiciMAD — station info (GBFS)",
        url="https://gbfs.urbansharing.com/bicimad.com/station_information.json",
        lat_field="lat",
        lon_field="lon",
        label_field="name",
        poll_ms=60000,
        icon="🚲",
        icon_color="#f97316",
    ),
    _Preset(
        name="OpenSky — Flights over Spain (free tier)",
        url="https://opensky-network.org/api/states/all?lamin=36&lomin=-9&lamax=44&lomax=4",
        lat_field="lat",
        lon_field="lon",
        label_field="callsign",
        poll_ms=12000,
        icon="✈",
        icon_color="#f43f5e",
        note="Rate-limited; anonymous tier allows ~1 req/10 s.",
    ),
    # ── Gijón / Asturias ─────────────────────────────────────────────────────
    _Preset(
        name="Gijón/Asturias — Flights Cantabrian Coast (OpenSky)",
        url="https://opensky-network.org/api/states/all?lamin=43.0&lomin=-7.0&lamax=44.5&lomax=-4.0",
        lat_field="lat",
        lon_field="lon",
        label_field="callsign",
        poll_ms=12000,
        icon="✈",
        icon_color="#22d3ee",
        note="Aircraft over Gijón, Asturias and the Bay of Biscay.",
    ),
    _Preset(
        name="Bay of Biscay — Ships AIS (AISHub free tier)",
        url="https://data.aishub.net/ws.php?username=REPLACE_USERNAME&format=1&output=json&compress=0&latmin=43.0&lonmin=-6.5&latmax=44.0&lonmax=-4.5",
        lat_field="LATITUDE",
        lon_field="LONGITUDE",
        label_field="NAME",
        poll_ms=60000,
        icon="🚢",
        icon_color="#3b82f6",
        note="Register free at aishub.net, then replace REPLACE_USERNAME in the URL before saving.",
    ),
    _Preset(
        name="Digitraffic — Finnish/Baltic AIS vessels (free, no key)",
        url="https://meri.digitraffic.fi/api/v1/locations/latest",
        lat_field="lat",
        lon_field="lon",
        label_field="name",
        poll_ms=30000,
        icon="🚢",
        icon_color="#38bdf8",
        note="Free public AIS feed. GeoJSON FeatureCollection. Covers Finnish & Baltic waters. No API key required.",
    ),
]


class LiveLayerDialog(QDialog):
    """Dialog for adding or editing a Live Feed layer.

    Parameters
    ----------
    layer:
        Existing LiveLayer to edit, or ``None`` to create a new one.
    """

    def __init__(
        self,
        layer: LiveLayer | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._layer = layer
        self.setWindowTitle(
            t("edit_live_feed") if layer else t("add_live_feed")
        )
        self.setMinimumWidth(480)
        self._build_ui()
        if layer:
            self._populate(layer)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        tabs = QTabWidget(self)
        tabs.addTab(self._make_feed_tab(), t("tab_feed"))
        tabs.addTab(self._make_style_tab(), t("tab_style"))
        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        add_dialog_help_button(buttons, self, "Live Feed window help")
        root.addWidget(buttons)

        self._buttons = buttons

    def _make_feed_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)

        # Quick-start preset picker
        self._preset_combo = QComboBox()
        self._preset_combo.addItem(t("preset_choose"), None)
        for p in _PRESETS:
            self._preset_combo.addItem(p.name, p)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.addWidget(self._preset_combo, 1)
        form.addRow(t("quick_start"), preset_row)

        sep0 = QFrame()
        sep0.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep0)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(t("feed_name_placeholder"))
        form.addRow(t("feed_name"), self._name_edit)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://api.example.com/vehicles")
        form.addRow(t("feed_url"), self._url_edit)

        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(500, 300_000)
        self._poll_spin.setSingleStep(500)
        self._poll_spin.setSuffix(" ms")
        self._poll_spin.setValue(5000)
        form.addRow(t("poll_interval"), self._poll_spin)

        self._auth_edit = QLineEdit()
        self._auth_edit.setPlaceholderText("Authorization: Bearer <token>")
        self._auth_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("auth_header"), self._auth_edit)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep)

        self._lat_edit = QLineEdit("lat")
        form.addRow(t("lat_field"), self._lat_edit)

        self._lon_edit = QLineEdit("lon")
        form.addRow(t("lon_field"), self._lon_edit)

        self._label_edit = QLineEdit("id")
        form.addRow(t("label_field"), self._label_edit)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep2)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton(t("test_connection"))
        self._test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self._test_btn)
        test_row.addStretch()
        form.addRow(test_row)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(100)
        self._preview.setPlaceholderText(t("test_preview_placeholder"))
        form.addRow(t("preview"), self._preview)

        return w

    def _make_style_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)

        # Icon gallery picker
        self._icon_combo = QComboBox()
        for glyph, label in _ICON_GALLERY:
            self._icon_combo.addItem(label, glyph)
        form.addRow(t("icon_type"), self._icon_combo)

        color_row = QHBoxLayout()
        color_row.setContentsMargins(0, 0, 0, 0)
        self._color_btn = _ColorButton()
        color_row.addWidget(self._color_btn)
        color_row.addStretch()
        form.addRow(t("icon_color"), color_row)

        self._size_spin = QSpinBox()
        self._size_spin.setRange(6, 40)
        self._size_spin.setValue(14)
        form.addRow(t("icon_size"), self._size_spin)

        self._trail_spin = QSpinBox()
        self._trail_spin.setRange(0, 200)
        self._trail_spin.setValue(0)
        self._trail_spin.setSpecialValueText(t("trail_off"))
        form.addRow(t("trail_length"), self._trail_spin)

        self._visible_chk = QCheckBox()
        self._visible_chk.setChecked(True)
        form.addRow(t("visible"), self._visible_chk)

        return w

    # ── Populate / collect ─────────────────────────────────────────────────────

    def _populate(self, layer: LiveLayer) -> None:
        self._name_edit.setText(layer.name)
        self._url_edit.setText(layer.feed_url)
        self._poll_spin.setValue(layer.poll_interval_ms)
        # Load auth from keyring (preferred) or fall back to model value
        from bimap.secrets import get_secret
        self._auth_edit.setText(
            get_secret(f"live_layer_{layer.id}") or layer.auth_header
        )
        self._lat_edit.setText(layer.lat_field)
        self._lon_edit.setText(layer.lon_field)
        self._label_edit.setText(layer.label_field)
        self._color_btn.set_color(layer.icon_color)
        self._size_spin.setValue(layer.icon_size)
        self._trail_spin.setValue(layer.trail_length)
        self._visible_chk.setChecked(layer.visible)
        # Set icon gallery selection
        icon_idx = next(
            (i for i, (g, _) in enumerate(_ICON_GALLERY) if g == layer.icon), 0
        )
        self._icon_combo.setCurrentIndex(icon_idx)

    def result_layer(self) -> LiveLayer:
        """Return the LiveLayer built from the dialog fields.

        Only valid to call after the dialog has been accepted.
        The auth header is saved to the OS keychain; the model stores an empty
        string so tokens are never written to the .bimap project file.
        """
        base_id = self._layer.id if self._layer else None
        auth_value = self._auth_edit.text().strip()
        kwargs = {
            "name": self._name_edit.text().strip() or t("unnamed_feed"),
            "feed_url": self._url_edit.text().strip(),
            "poll_interval_ms": self._poll_spin.value(),
            "auth_header": "",  # stored in keyring, not in project file
            "lat_field": self._lat_edit.text().strip() or "lat",
            "lon_field": self._lon_edit.text().strip() or "lon",
            "label_field": self._label_edit.text().strip() or "id",
            "icon": self._icon_combo.currentData() or "●",
            "icon_color": self._color_btn.color(),
            "icon_size": self._size_spin.value(),
            "trail_length": self._trail_spin.value(),
            "visible": self._visible_chk.isChecked(),
        }
        if base_id:
            kwargs["id"] = base_id
        layer = LiveLayer(**kwargs)
        # Persist auth header in OS keychain keyed by layer ID
        from bimap.secrets import set_secret
        set_secret(f"live_layer_{layer.id}", auth_value)
        return layer

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_preset_selected(self, index: int) -> None:
        """Auto-fill feed fields when a Quick Start preset is chosen."""
        preset: _Preset | None = self._preset_combo.itemData(index)
        if preset is None:
            return
        self._name_edit.setText(preset.name)
        self._url_edit.setText(preset.url)
        self._poll_spin.setValue(preset.poll_ms)
        self._auth_edit.setText(preset.auth_header)
        self._lat_edit.setText(preset.lat_field)
        self._lon_edit.setText(preset.lon_field)
        self._label_edit.setText(preset.label_field)
        self._color_btn.set_color(preset.icon_color)
        icon_idx = next(
            (i for i, (g, _) in enumerate(_ICON_GALLERY) if g == preset.icon), 0
        )
        self._icon_combo.setCurrentIndex(icon_idx)
        if preset.note:
            self._preview.setPlainText(f"ℹ {preset.note}")

    def _on_ok(self) -> None:
        name = self._name_edit.text().strip()
        url = self._url_edit.text().strip()
        if not name:
            self._name_edit.setFocus()
            return
        if not url:
            self._url_edit.setFocus()
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                t("Invalid URL"),
                t("URL must start with http:// or https://"),
            )
            self._url_edit.setFocus()
            return
        self.accept()

    def _test_connection(self) -> None:
        """Fire a one-shot request using QNetworkAccessManager and show raw JSON."""
        url = self._url_edit.text().strip()
        if not url:
            self._preview.setPlainText(t("enter_url_first"))
            return

        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
        except ImportError:
            self._preview.setPlainText(t("network_unavailable"))
            return

        self._test_btn.setEnabled(False)
        self._preview.setPlainText(t("connecting"))

        nam = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(url))
        auth = self._auth_edit.text().strip()
        if auth and ":" in auth:
            hname, _, hval = auth.partition(":")
            req.setRawHeader(hname.strip().encode(), hval.strip().encode())

        reply = nam.get(req)

        def _on_done(r=reply) -> None:
            self._test_btn.setEnabled(True)
            if r.error().value != 0:  # type: ignore[union-attr]
                self._preview.setPlainText(f"Error: {r.errorString()}")
                r.deleteLater()
                return
            raw = bytes(r.readAll()).decode("utf-8", errors="replace")
            try:
                pretty = json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
                self._preview.setPlainText(pretty[:4000])
            except Exception:
                self._preview.setPlainText(raw[:4000])
            r.deleteLater()

        reply.finished.connect(_on_done)
