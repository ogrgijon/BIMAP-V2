"""OGC Web Map Service (WMS) data source connector.

Exposes a WMS endpoint in two modes — both return flat row dicts, exactly as
the WFS connector does, so field-mapping and data panels work identically.

──────────────────────────────────────────────────────────────────────────────
Mode 1 — Layer Catalogue  (layer_name = "")
──────────────────────────────────────────────────────────────────────────────
``fetch()`` issues a GetCapabilities request and returns one row per
advertised layer.  Useful for browsing what a service offers.

Row columns:
  _layer_name   – layer Name element (the identifier)
  _title        – human-readable title
  _abstract     – layer abstract / description
  _crs_list     – space-separated list of supported CRS codes
  _bbox_west    – WGS84 western longitude
  _bbox_east    – WGS84 eastern longitude
  _bbox_south   – WGS84 southern latitude
  _bbox_north   – WGS84 northern latitude
  _lat          – bbox centre latitude  (maps to a point on the canvas)
  _lon          – bbox centre longitude
  _attribution  – attribution text if declared
  _queryable    – "true"/"false" — whether GetFeatureInfo is supported

──────────────────────────────────────────────────────────────────────────────
Mode 2 — GetFeatureInfo  (layer_name set + bbox set)
──────────────────────────────────────────────────────────────────────────────
``fetch()`` queries GetFeatureInfo at the centre pixel of *bbox*.  The
response is parsed and returned as rows of key/value pairs.

Row columns depend on the server response.  Guaranteed columns:
  _layer_name  – the queried layer
  _lat / _lon  – centre of the queried bbox
  … all feature attributes from the GetFeatureInfo response

Connection parameters
──────────────────────────────────────────────────────────────────────────────
  url          – WMS base URL (no query string needed; stripped on init)
  layer_name   – Name of the layer to query (blank → catalogue mode)
  styles       – Comma-separated styles string (optional, default empty)
  bbox         – ``minx,miny,maxx,maxy`` in WGS84 (optional)
  info_format  – MIME type for GetFeatureInfo (default application/json)
  width        – Pixel width used in GetFeatureInfo requests (default 101)
  height       – Pixel height used in GetFeatureInfo requests (default 101)
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

import requests

from bimap.config import HTTP_HEADERS
from bimap.data.base import DataSourceBase

# Namespaces that appear in WMS responses
_WMS_NS = {
    "wms": "http://www.opengis.net/wms",
    "ows": "http://www.opengis.net/ows/1.1",
}


# ── GetCapabilities XML helpers ───────────────────────────────────────────────

def _text(el: ET.Element, *local_names: str) -> str:
    """Return stripped text of the first matching child by local name."""
    for child in el:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in local_names and child.text:
            return child.text.strip()
    return ""


def _attr(el: ET.Element, *attr_names: str) -> str:
    for a in attr_names:
        if el.get(a):
            return el.get(a, "")  # type: ignore[return-value]
    return ""


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_layers(root: ET.Element) -> list[dict[str, Any]]:
    """Recursively walk <Layer> elements in a GetCapabilities response."""
    layers: list[dict[str, Any]] = []

    def _walk(el: ET.Element) -> None:
        if _local(el.tag) != "Layer":
            return
        name = _text(el, "Name")
        if not name:
            # Container layer without a Name — recurse only
            for child in el:
                _walk(child)
            return

        layer: dict[str, Any] = {
            "_layer_name": name,
            "_title": _text(el, "Title"),
            "_abstract": _text(el, "Abstract"),
            "_queryable": _attr(el, "queryable") or "0",
            "_attribution": "",
            "_crs_list": "",
            "_bbox_west": "",
            "_bbox_east": "",
            "_bbox_south": "",
            "_bbox_north": "",
            "_lat": "",
            "_lon": "",
        }

        # CRS / SRS (may be multiple elements)
        crs_codes: list[str] = []
        for child in el:
            ltag = _local(child.tag)
            if ltag in ("CRS", "SRS") and child.text:
                crs_codes.append(child.text.strip())
        layer["_crs_list"] = " ".join(crs_codes)

        # WMS 1.3 EX_GeographicBoundingBox
        for child in el:
            if _local(child.tag) == "EX_GeographicBoundingBox":
                layer["_bbox_west"] = _text(child, "westBoundLongitude")
                layer["_bbox_east"] = _text(child, "eastBoundLongitude")
                layer["_bbox_south"] = _text(child, "southBoundLatitude")
                layer["_bbox_north"] = _text(child, "northBoundLatitude")
                break

        # WMS 1.1 LatLonBoundingBox (fallback if not already filled)
        if not layer["_bbox_west"]:
            for child in el:
                if _local(child.tag) == "LatLonBoundingBox":
                    layer["_bbox_west"] = child.get("minx", "")
                    layer["_bbox_east"] = child.get("maxx", "")
                    layer["_bbox_south"] = child.get("miny", "")
                    layer["_bbox_north"] = child.get("maxy", "")
                    break

        # Compute centre
        try:
            lat = (float(layer["_bbox_south"]) + float(layer["_bbox_north"])) / 2
            lon = (float(layer["_bbox_west"]) + float(layer["_bbox_east"])) / 2
            layer["_lat"] = str(round(lat, 7))
            layer["_lon"] = str(round(lon, 7))
        except (ValueError, ZeroDivisionError):
            pass

        # Attribution
        for child in el:
            if _local(child.tag) == "Attribution":
                layer["_attribution"] = _text(child, "Title") or ""
                break

        # Styles — collect <Style><Name> values
        style_names: list[str] = []
        for child in el:
            if _local(child.tag) == "Style":
                sname = _text(child, "Name")
                if sname:
                    style_names.append(sname)
        layer["_styles"] = ",".join(style_names)

        # Normalise queryable flag
        layer["_queryable"] = "true" if layer["_queryable"] in ("1", "true") else "false"

        layers.append(layer)
        for child in el:
            _walk(child)

    # The WMS Capability element or root itself
    for top in root.iter():
        if _local(top.tag) == "Capability":
            for child in top:
                _walk(child)
            return layers
    # Fallback: walk the entire root
    for child in root:
        _walk(child)
    return layers


def _parse_feature_info_json(text: str, layer_name: str, lat: str, lon: str) -> list[dict]:
    """Parse a JSON GetFeatureInfo response."""
    rows: list[dict] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return rows
    features = data.get("features", [data] if isinstance(data, dict) else [])
    for feat in features:
        props = {}
        if isinstance(feat, dict):
            props = feat.get("properties") or feat
        row: dict[str, Any] = {
            "_layer_name": layer_name,
            "_lat": lat,
            "_lon": lon,
            "_geom_type": "Point",
            "_coordinates": json.dumps([float(lon), float(lat)])  # GeoJSON Point format
        }
        if isinstance(props, dict):
            row.update(props)
        rows.append(row)
    return rows


def _parse_feature_info_text(text: str, layer_name: str, lat: str, lon: str) -> list[dict]:
    """Parse a plain-text or GML GetFeatureInfo response as key=value rows."""
    rows: list[dict] = []
    row: dict[str, Any] = {
        "_layer_name": layer_name,
        "_lat": lat,
        "_lon": lon,
        "_geom_type": "Point",
        "_coordinates": json.dumps([float(lon), float(lat)])  # GeoJSON Point format
    }
    in_feature = False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # GML: look for feature members
        if "<" in line and ">" in line:
            # Simple-value GML
            try:
                el = ET.fromstring(f"<root>{line}</root>")
                for child in el:
                    tag = _local(child.tag)
                    if child.text and child.text.strip():
                        row[tag] = child.text.strip()
                in_feature = True
            except ET.ParseError:
                pass
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            row[key.strip()] = val.strip()
            in_feature = True
        elif in_feature and line == "":
            if len(row) > 5:  # More than just the base fields
                rows.append(row)
                row = {
                    "_layer_name": layer_name,
                    "_lat": lat,
                    "_lon": lon,
                    "_geom_type": "Point",
                    "_coordinates": json.dumps([float(lon), float(lat)])
                }
            in_feature = False
    if len(row) > 5:
        rows.append(row)
    return rows


# ── WMS connector ─────────────────────────────────────────────────────────────

class WmsSource(DataSourceBase):
    """Loads data from an OGC WMS endpoint.

    Parameters
    ----------
    url:
        Base URL of the WMS service.
    layer_name:
        Name of the layer to query via GetFeatureInfo.
        Empty string → GetCapabilities layer-catalogue mode.
    styles:
        Comma-separated style names (optional, passed through to requests).
    bbox:
        ``"minx,miny,maxx,maxy"`` in WGS84.  Required for GetFeatureInfo.
        Used to derive the map extent and the query pixel coordinates.
    info_format:
        MIME type for GetFeatureInfo response.  Falls back to ``text/plain``.
    width / height:
        Pixel dimensions of the virtual map image used in GetFeatureInfo.
        The query pixel is the centre: ``I = width // 2``, ``J = height // 2``.
    """

    def __init__(
        self,
        url: str,
        layer_name: str = "",
        styles: str = "",
        bbox: str = "",
        info_format: str = "application/json",
        width: int = 101,
        height: int = 101,
    ) -> None:
        self._url = url.rstrip("?& ")
        self._layer_name = layer_name.strip()
        self._styles = styles
        self._bbox = bbox.strip()
        self._info_format = info_format or "application/json"
        self._width = max(1, int(width))
        self._height = max(1, int(height))
        self._rows: list[dict[str, Any]] = []
        self._columns: list[str] = []
        self._layers: list[dict[str, Any]] = []
        self._version: str = "1.3.0"
        self._extent: list[float] = []  # [min_lat, min_lon, max_lat, max_lon]

    # ── DataSourceBase interface ─────────────────────────────────────────────

    def connect(self) -> None:
        """Validate the endpoint by fetching GetCapabilities."""
        params = {
            "SERVICE": "WMS",
            "REQUEST": "GetCapabilities",
        }
        try:
            resp = requests.get(
                self._url, params=params, headers=HTTP_HEADERS, timeout=15
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(f"WMS connect failed: {exc}") from exc
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            raise ValueError(f"WMS GetCapabilities parse error: {exc}") from exc
        # Detect WMS version from root attribute
        ver = root.get("version", "1.3.0")
        self._version = ver
        self._layers = _parse_layers(root)
        if not self._layers:
            raise ValueError("WMS service returned no queryable layers in GetCapabilities.")
        # Compute extent from layer bboxes
        lats: list[float] = []
        lons: list[float] = []
        for lyr in self._layers:
            # Restrict to the configured layer if one is set
            if self._layer_name and lyr["_layer_name"] != self._layer_name:
                continue
            try:
                lats += [float(lyr["_bbox_south"]), float(lyr["_bbox_north"])]
                lons += [float(lyr["_bbox_west"]), float(lyr["_bbox_east"])]
            except (ValueError, TypeError, KeyError):
                pass
        if not lats:  # fall back to all layers
            for lyr in self._layers:
                try:
                    lats += [float(lyr["_bbox_south"]), float(lyr["_bbox_north"])]
                    lons += [float(lyr["_bbox_west"]), float(lyr["_bbox_east"])]
                except (ValueError, TypeError, KeyError):
                    pass
        if lats:
            self._extent = [min(lats), min(lons), max(lats), max(lons)]

    def fetch(self) -> list[dict[str, Any]]:
        """Fetch data from the WMS endpoint.

        - If *layer_name* is empty: returns all layers as metadata rows.
        - If *layer_name* + *bbox* are set: runs GetFeatureInfo at the bbox
          centre and returns feature attribute rows.
        """
        if not self._layers:
            # auto-connect if caller skipped connect()
            self.connect()

        if not self._layer_name:
            # Catalogue mode — return layer metadata as rows
            self._rows = list(self._layers)
        else:
            self._rows = self._get_feature_info()

        self._columns = list(self._rows[0].keys()) if self._rows else []
        return self._rows

    def get_columns(self) -> list[str] | None:
        return self._columns or None

    def get_extent(self) -> list[float] | None:
        """Return [min_lat, min_lon, max_lat, max_lon] from GetCapabilities."""
        return self._extent if self._extent else None

    def disconnect(self) -> None:
        self._rows = []
        self._columns = []

    # ── Helpers ──────────────────────────────────────────────────────────────

    def get_layers(self) -> list[dict[str, Any]]:
        """Return layer metadata dicts discovered in GetCapabilities."""
        return list(self._layers)

    def fetch_map_image(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        width: int,
        height: int,
    ) -> bytes | None:
        """Issue a WMS GetMap request for the given viewport.

        Tries WMS 1.3.0 with CRS:84 first (avoids EPSG:4326 axis-order
        ambiguity in 1.3.0); falls back to WMS 1.1.1 + EPSG:4326 if the
        server returns a non-image response (e.g. a ServiceException).

        Returns raw PNG bytes on success, ``None`` on any error.
        """
        if not self._layer_name:
            return None

        # Attempts in preference order:
        #  1. WMS 1.1.1 + SRS=EPSG:4326  (lon/lat) — most compatible with GeoServer
        #  2. WMS 1.3.0 + CRS=CRS:84     (lon/lat)  — OGC standard, some modern servers
        #  3. WMS 1.3.0 + CRS=EPSG:4326  (lat/lon axis-swap) — strict WMS 1.3.0 servers
        attempts: list[tuple[str, str, str, float, float, float, float]] = [
            ("1.1.1", "SRS", "EPSG:4326", min_lon, min_lat, max_lon, max_lat),
            ("1.3.0", "CRS", "CRS:84",    min_lon, min_lat, max_lon, max_lat),
            ("1.3.0", "CRS", "EPSG:4326", min_lat, min_lon, max_lat, max_lon),  # axis-swap
        ]
        last_error: str = ""
        for version, crs_param, crs_value, bx0, by0, bx1, by1 in attempts:
            params: dict[str, Any] = {
                "SERVICE": "WMS",
                "VERSION": version,
                "REQUEST": "GetMap",
                "LAYERS": self._layer_name,
                "STYLES": self._styles or "",
                crs_param: crs_value,
                "BBOX": f"{bx0},{by0},{bx1},{by1}",
                "WIDTH": str(width),
                "HEIGHT": str(height),
                "FORMAT": "image/png",
                "TRANSPARENT": "TRUE",
            }
            try:
                resp = requests.get(
                    self._url, params=params, headers=HTTP_HEADERS, timeout=15
                )
                resp.raise_for_status()
                ct = resp.headers.get("Content-Type", "")
                if "image" in ct:
                    return resp.content
                # Server returned non-image (likely XML ServiceException) — try next
                last_error = f"Unexpected Content-Type '{ct}' for {version}/{crs_value}"
            except requests.RequestException as exc:
                last_error = str(exc)
        raise RuntimeError(f"WMS GetMap failed after all attempts. Last error: {last_error}")

    def _get_feature_info(self) -> list[dict[str, Any]]:
        """Run GetFeatureInfo at the centre of *self._bbox*."""
        if not self._bbox:
            # No bbox → fall back to catalogue row for the named layer
            for layer in self._layers:
                if layer["_layer_name"] == self._layer_name:
                    return [layer]
            return []

        parts = [p.strip() for p in self._bbox.split(",")]
        if len(parts) != 4:
            raise ValueError(f"Invalid bbox for WMS GetFeatureInfo: {self._bbox!r}")
        try:
            minx, miny, maxx, maxy = [float(p) for p in parts]
        except ValueError as exc:
            raise ValueError(f"Non-numeric bbox value: {exc}") from exc

        # Centre pixel
        cx = self._width // 2
        cy = self._height // 2
        lat_c = str(round((miny + maxy) / 2, 7))
        lon_c = str(round((minx + maxx) / 2, 7))

        # WMS 1.3 uses BBOX as CRS:miny,minx,maxy,maxx for EPSG:4326
        # For simplicity we always send as minx,miny,maxx,maxy in CRS:84 / EPSG:4326
        params: dict[str, Any] = {
            "SERVICE": "WMS",
            "VERSION": self._version,
            "REQUEST": "GetFeatureInfo",
            "LAYERS": self._layer_name,
            "QUERY_LAYERS": self._layer_name,
            "STYLES": self._styles,
            "BBOX": self._bbox,
            "WIDTH": self._width,
            "HEIGHT": self._height,
            "INFO_FORMAT": self._info_format,
            "FEATURE_COUNT": 10,
        }
        # WMS 1.3: CRS + I,J; WMS 1.1: SRS + X,Y
        if self._version.startswith("1.3"):
            params["CRS"] = "CRS:84"
            params["I"] = cx
            params["J"] = cy
        else:
            params["SRS"] = "EPSG:4326"
            params["X"] = cx
            params["Y"] = cy

        try:
            resp = requests.get(
                self._url, params=params, headers=HTTP_HEADERS, timeout=20
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(f"WMS GetFeatureInfo failed: {exc}") from exc

        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type or resp.text.lstrip().startswith("{"):
            rows = _parse_feature_info_json(resp.text, self._layer_name, lat_c, lon_c)
        else:
            rows = _parse_feature_info_text(resp.text, self._layer_name, lat_c, lon_c)

        # If no attribute rows were parsed, return a single metadata row
        if not rows:
            for layer in self._layers:
                if layer["_layer_name"] == self._layer_name:
                    # Add GeoJSON fields to layer metadata
                    layer["_geom_type"] = "Point"
                    layer["_coordinates"] = json.dumps([float(lon_c), float(lat_c)])
                    return [layer]
            return [{
                "_layer_name": self._layer_name,
                "_lat": lat_c,
                "_lon": lon_c,
                "_geom_type": "Point",
                "_coordinates": json.dumps([float(lon_c), float(lat_c)])
            }]
        return rows
