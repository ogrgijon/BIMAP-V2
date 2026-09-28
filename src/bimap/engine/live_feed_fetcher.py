"""Live feed poller — polls REST endpoints on configurable timers.

Uses QNetworkAccessManager (non-blocking, main thread) to avoid
cross-thread QPainter issues.  One QTimer is kept per active LiveLayer.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from bimap.config import APP_VERSION
from bimap.engine._utils import get_nested
from bimap.models.live_layer import LiveLayer


class LiveFeedFetcher(QObject):
    """Manages polling timers for all active LiveLayer feeds.

    Signals
    -------
    positions_updated(layer_id, positions)
        Emitted after a successful fetch with a list of position dicts.
    fetch_error(layer_id, error_msg)
        Emitted when a fetch fails (network error or JSON parse error).
    """

    positions_updated = pyqtSignal(str, list)   # layer_id, list[dict]
    fetch_error = pyqtSignal(str, str)           # layer_id, error_msg

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._timers: dict[str, QTimer] = {}
        self._layers: dict[str, LiveLayer] = {}
        self._timeout_ms: int = 10_000

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_timeout(self, ms: int) -> None:
        self._timeout_ms = ms

    def start(self, layer: LiveLayer) -> None:
        """Start polling for the given layer (restarts if already running)."""
        self.stop(layer.id)
        self._layers[layer.id] = layer
        timer = QTimer(self)
        timer.setInterval(layer.poll_interval_ms)
        timer.timeout.connect(lambda lid=layer.id: self._poll(lid))
        timer.start()
        self._timers[layer.id] = timer
        self._poll(layer.id)   # immediate first poll

    def stop(self, layer_id: str) -> None:
        """Stop polling for a layer."""
        if layer_id in self._timers:
            self._timers[layer_id].stop()
            self._timers[layer_id].deleteLater()
            del self._timers[layer_id]
        self._layers.pop(layer_id, None)

    def stop_all(self) -> None:
        """Stop all active pollers."""
        for lid in list(self._timers.keys()):
            self.stop(lid)

    def force_poll(self, layer_id: str) -> None:
        """Immediately fetch one update for the given layer."""
        if layer_id in self._layers:
            self._poll(layer_id)

    def update_layer(self, layer: LiveLayer) -> None:
        """Replace config for a running layer (restarts its timer)."""
        if layer.id in self._timers:
            self.start(layer)
        else:
            self._layers[layer.id] = layer

    def is_active(self, layer_id: str) -> bool:
        return layer_id in self._timers

    # ── Internal ───────────────────────────────────────────────────────────────

    def _poll(self, layer_id: str) -> None:
        layer = self._layers.get(layer_id)
        if layer is None:
            return
        req = QNetworkRequest(QUrl(layer.feed_url))
        req.setHeader(
            QNetworkRequest.KnownHeaders.UserAgentHeader,
            f"BIMAP/{APP_VERSION} (https://github.com/ogrgijon/BIMAP)",
        )
        req.setTransferTimeout(self._timeout_ms)
        # Resolve auth header — prefer keyring over plaintext stored in model
        from bimap.secrets import get_secret
        auth_header = get_secret(f"live_layer_{layer.id}") or layer.auth_header
        if auth_header and ":" in auth_header:
            hname, _, hval = auth_header.partition(":")
            req.setRawHeader(hname.strip().encode(), hval.strip().encode())
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply, lid=layer_id: self._on_reply(r, lid))

    def _on_reply(self, reply: QNetworkReply, layer_id: str) -> None:
        layer = self._layers.get(layer_id)
        if layer is None:
            reply.deleteLater()
            return
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.fetch_error.emit(layer_id, reply.errorString())
            reply.deleteLater()
            return
        try:
            raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
            data = json.loads(raw)
            positions = self._parse_positions(data, layer)
            self.positions_updated.emit(layer_id, positions)
        except Exception as exc:
            self.fetch_error.emit(layer_id, str(exc))
        finally:
            reply.deleteLater()

    @staticmethod
    def _parse_opensky_states(states: list) -> list[dict]:
        """Convert OpenSky array-of-arrays to normalised position dicts.

        OpenSky column order (v1 REST API):
          0 icao24, 1 callsign, 2 origin_country,
          3 time_position, 4 last_contact,
          5 longitude, 6 latitude,
          7 baro_altitude, 8 on_ground,
          9 velocity, 10 true_track, ...
        """
        positions: list[dict] = []
        for row in states:
            if not isinstance(row, (list, tuple)) or len(row) < 7:
                continue
            lon_, lat_ = row[5], row[6]
            if lon_ is None or lat_ is None:
                continue
            try:
                lat = float(lat_)
                lon = float(lon_)
            except (TypeError, ValueError):
                continue
            positions.append({
                "lat": lat,
                "lon": lon,
                "label": str(row[1] or row[0] or "").strip(),
                "speed": row[9] if len(row) > 9 else None,
                "heading": row[10] if len(row) > 10 else None,
            })
        return positions

    # Extended envelope keys (beyond the original set)
    _ENVELOPE_KEYS = (
        "data", "result", "results", "items", "features", "states",
        "ac", "aircraft", "vehicles", "vehicle", "vessels", "vessel",
        "buses", "trains", "stations", "markers", "entity",
    )
    # GBFS inner keys (when top-level `data` is a dict, not a list)
    _GBFS_INNER_KEYS = ("stations", "bikes", "vehicles", "items", "features")

    @classmethod
    def _parse_positions(cls, data: object, layer: LiveLayer) -> list[dict]:
        """Extract a flat list of position dicts from arbitrary JSON.

        Handles:
        - Plain array root
        - Dict with common envelope key (data/result/items/features/state/ac/…)
        - GBFS nested structure: ``{"data": {"stations": [{lat, lon}]}}``
        - OpenSky array-of-arrays: ``{"states": [[icao, callsign, …, lon, lat]]}``
        - Dotted field-path notation for lat/lon (e.g. ``"iss_position.latitude"``)
        """
        # Flatten GeoJSON FeatureCollection into regular [{lat, lon, ...properties}]
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            flat_rows: list[dict] = []
            for feat in data.get("features", []):
                coords = (feat.get("geometry") or {}).get("coordinates") or []
                if len(coords) < 2:
                    continue
                flat = dict(feat.get("properties") or {})
                flat["lat"] = float(coords[1])  # GeoJSON is [lon, lat]
                flat["lon"] = float(coords[0])
                flat_rows.append(flat)
            rows = flat_rows
        else:
            rows = []

        if not rows and isinstance(data, list):
            rows = data
        elif not rows and isinstance(data, dict):
            for key in cls._ENVELOPE_KEYS:
                if key not in data:
                    continue
                val = data[key]
                if isinstance(val, list):
                    # OpenSky special case: states is a list of arrays
                    if key == "states" and val and isinstance(val[0], (list, tuple)):
                        return cls._parse_opensky_states(val)
                    rows = val
                    break
                # GBFS: data key maps to a nested dict containing a list
                if isinstance(val, dict):
                    for inner_key in cls._GBFS_INNER_KEYS:
                        if inner_key in val and isinstance(val[inner_key], list):
                            rows = val[inner_key]
                            break
                    if rows:
                        break
            if not rows:
                rows = [data]

        positions: list[dict] = []
        lat_key = layer.lat_field
        lon_key = layer.lon_field
        label_key = layer.label_field
        use_dotted = "." in lat_key or "." in lon_key or "." in label_key

        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                if use_dotted:
                    lat_raw = get_nested(row, lat_key)
                    lon_raw = get_nested(row, lon_key)
                else:
                    lat_raw = row.get(lat_key)
                    lon_raw = row.get(lon_key)
                lat = float(lat_raw)  # type: ignore[arg-type]
                lon = float(lon_raw)  # type: ignore[arg-type]
            except (KeyError, TypeError, ValueError):
                continue
            if use_dotted:
                label_raw = get_nested(row, label_key)
            else:
                label_raw = row.get(label_key, "")
            pos: dict = {
                "lat": lat,
                "lon": lon,
                "label": str(label_raw or ""),
                "speed": row.get("speed") or row.get("velocity") or row.get("sog"),
                "heading": row.get("heading") or row.get("true_track") or row.get("cog") or row.get("bearing"),
            }
            # Pass through any extra fields for extension use
            pos.update({k: v for k, v in row.items() if k not in pos})
            positions.append(pos)
        return positions
