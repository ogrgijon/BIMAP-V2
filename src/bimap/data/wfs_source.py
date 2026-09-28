"""OGC Web Feature Service (WFS) data source connector.

Fetches vector features from a WFS 2.0 / 1.1 / 1.0 endpoint and returns them
as a flat list of row dicts suitable for field-mapping.

Each row contains:
- ``_geom_type``   – geometry type reported by the service
- ``_lat``         – centroid latitude  (float as str, present for Point/all)
- ``_lon``         – centroid longitude (float as str, present for Point/all)
- ``_coordinates`` – JSON-encoded raw coordinate array
- All feature properties from the service
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

import requests

from bimap.config import HTTP_HEADERS
from bimap.data.base import DataSourceBase

# XML namespaces commonly used in WFS responses
_NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "wfs1": "http://www.opengis.net/wfs",
    "gml": "http://www.opengis.net/gml/3.2",
    "gml2": "http://www.opengis.net/gml",
    "ows": "http://www.opengis.net/ows/1.1",
}


def _parse_capabilities_feature_types(xml_text: str) -> list[str]:
    """Return list of FeatureType names from WFS GetCapabilities response."""
    return [ft["name"] for ft in _parse_capabilities_full(xml_text)]


def _parse_capabilities_full(xml_text: str) -> list[dict]:
    """Return list of dicts with 'name' and optional WGS84 bbox keys."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    result: list[dict] = []
    for ft in root.iter():
        if ft.tag.endswith("}FeatureType") or ft.tag == "FeatureType":
            entry: dict = {}
            for child in ft:
                local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if local == "Name" and child.text:
                    entry["name"] = child.text.strip()
                elif local == "Title" and child.text:
                    entry["title"] = child.text.strip()
                # WFS 2.0: <WGS84BoundingBox>
                elif local == "WGS84BoundingBox":
                    lower = upper = None
                    for bb in child:
                        bl = bb.tag.split("}")[-1] if "}" in bb.tag else bb.tag
                        if bl == "LowerCorner" and bb.text:
                            lower = bb.text.strip().split()
                        elif bl == "UpperCorner" and bb.text:
                            upper = bb.text.strip().split()
                    if lower and upper and len(lower) == 2 and len(upper) == 2:
                        try:
                            # WGS84BoundingBox uses lon lat order
                            entry["min_lon"] = float(lower[0])
                            entry["min_lat"] = float(lower[1])
                            entry["max_lon"] = float(upper[0])
                            entry["max_lat"] = float(upper[1])
                        except ValueError:
                            pass
                # WFS 1.x: <LatLongBoundingBox minx miny maxx maxy>
                elif local == "LatLongBoundingBox":
                    try:
                        entry["min_lon"] = float(child.get("minx", ""))
                        entry["min_lat"] = float(child.get("miny", ""))
                        entry["max_lon"] = float(child.get("maxx", ""))
                        entry["max_lat"] = float(child.get("maxy", ""))
                    except (ValueError, TypeError):
                        pass
            if "name" in entry:
                result.append(entry)
    return result


def _centroid(coords: Any, geom_type: str) -> tuple[float | None, float | None]:
    """Return (lon, lat) centroid from a GeoJSON coordinate array."""
    try:
        if geom_type == "Point":
            return float(coords[0]), float(coords[1])
        if geom_type in ("LineString", "MultiPoint"):
            flat = coords
            lons = [c[0] for c in flat]
            lats = [c[1] for c in flat]
            return sum(lons) / len(lons), sum(lats) / len(lats)
        if geom_type == "Polygon":
            ring = coords[0]
            lons = [c[0] for c in ring]
            lats = [c[1] for c in ring]
            return sum(lons) / len(lons), sum(lats) / len(lats)
        if geom_type in ("MultiPolygon", "MultiLineString"):
            # average first ring of first polygon
            ring = coords[0][0]
            lons = [c[0] for c in ring]
            lats = [c[1] for c in ring]
            return sum(lons) / len(lons), sum(lats) / len(lats)
    except (TypeError, IndexError, ZeroDivisionError):
        pass
    return None, None


class WfsSource(DataSourceBase):
    """Loads features from an OGC WFS endpoint.

    Parameters
    ----------
    url:
        Base URL of the WFS service (without query parameters).
    type_name:
        Feature type to fetch (``TYPENAME`` / ``TYPENAMES`` parameter).
        If empty, the first advertised feature type is used.
    max_features:
        Maximum number of features to return (passed as ``COUNT`` / ``MAXFEATURES``).
    bbox:
        Optional bounding box filter as ``"minx,miny,maxx,maxy"`` string (WGS84).
    cql_filter:
        Optional CQL filter expression string.
    """

    def __init__(
        self,
        url: str,
        type_name: str = "",
        max_features: int = 500,
        bbox: str = "",
        cql_filter: str = "",
    ) -> None:
        self._url = url.rstrip("?& ")
        self._type_name = type_name
        self._max_features = max_features
        self._bbox = bbox
        self._cql_filter = cql_filter
        self._rows: list[dict[str, Any]] = []
        self._columns: list[str] = []
        self._feature_types: list[str] = []
        self._extent: list[float] = []  # [min_lat, min_lon, max_lat, max_lon]

    # ── DataSourceBase interface ─────────────────────────────────────────────

    def connect(self) -> None:
        """Validate the endpoint by fetching GetCapabilities."""
        params = {
            "SERVICE": "WFS",
            "REQUEST": "GetCapabilities",
        }
        try:
            resp = requests.get(
                self._url, params=params, headers=HTTP_HEADERS, timeout=15
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(f"WFS connect failed: {exc}") from exc
        ft_list = _parse_capabilities_full(resp.text)
        self._feature_types = [ft["name"] for ft in ft_list]
        if not self._type_name and self._feature_types:
            self._type_name = self._feature_types[0]
        # Compute union extent from all feature types (or just the selected one)
        lats, lons = [], []
        for ft in ft_list:
            if "min_lat" in ft:
                if not self._type_name or ft["name"] == self._type_name:
                    lats += [ft["min_lat"], ft["max_lat"]]
                    lons += [ft["min_lon"], ft["max_lon"]]
        if not lats:  # fall back to union of all types
            for ft in ft_list:
                if "min_lat" in ft:
                    lats += [ft["min_lat"], ft["max_lat"]]
                    lons += [ft["min_lon"], ft["max_lon"]]
        if lats:
            self._extent = [min(lats), min(lons), max(lats), max(lons)]

    def fetch(self) -> list[dict[str, Any]]:
        """Fetch features and return as a flat list of row dicts."""
        if not self._type_name:
            raise ValueError("No feature type specified for WFS source.")

        params: dict[str, Any] = {
            "SERVICE": "WFS",
            "REQUEST": "GetFeature",
            "TYPENAMES": self._type_name,   # WFS 2.0
            "TYPENAME": self._type_name,    # WFS 1.x (servers ignore unknown params)
            "COUNT": self._max_features,    # WFS 2.0
            "MAXFEATURES": self._max_features,  # WFS 1.x
        }
        if self._bbox:
            params["BBOX"] = self._bbox
        if self._cql_filter:
            params["CQL_FILTER"] = self._cql_filter

        # Try output formats in preference order; stop at first successful parse
        _OUTPUT_FORMATS = [
            "application/json",
            "application/geo+json",
            "json",
            "GML3",
            "GML2",
            "text/xml; subtype=gml/3.2",
        ]
        last_exc: Exception | None = None
        rows: list[dict[str, Any]] = []
        for fmt in _OUTPUT_FORMATS:
            params["OUTPUTFORMAT"] = fmt
            try:
                resp = requests.get(
                    self._url, params=params, headers=HTTP_HEADERS, timeout=30
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                last_exc = exc
                continue

            content_type = resp.headers.get("Content-Type", "")
            text = resp.text
            if "json" in content_type or text.lstrip().startswith("{"):
                try:
                    rows = self._parse_geojson(resp.json())
                    break
                except Exception as exc:
                    last_exc = exc
                    continue
            elif "xml" in content_type or text.lstrip().startswith("<"):
                # Skip obvious WFS exception reports and try next format
                if "ExceptionReport" in text[:500] and "OUTPUTFORMAT" in text[:500]:
                    continue
                rows = self._parse_gml(text)
                if rows or "<wfs:FeatureCollection" in text:
                    break
            else:
                continue

        if not rows and last_exc is not None and not any(True for _ in rows):
            # All formats failed — surface the last network error
            raise ValueError(f"WFS fetch failed (tried all output formats): {last_exc}") from last_exc

        self._rows = rows
        self._columns = list(rows[0].keys()) if rows else []
        return rows

    def get_columns(self) -> list[str] | None:
        return self._columns or None

    def get_extent(self) -> list[float] | None:
        """Return [min_lat, min_lon, max_lat, max_lon] from GetCapabilities."""
        return self._extent if self._extent else None

    def disconnect(self) -> None:
        self._rows = []
        self._columns = []

    # ── Helpers ──────────────────────────────────────────────────────────────

    def get_feature_types(self) -> list[str]:
        """Return feature type names discovered in GetCapabilities."""
        return list(self._feature_types)

    @staticmethod
    def _parse_geojson(data: dict) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for feature in data.get("features", []):
            props: dict = feature.get("properties") or {}
            geom: dict = feature.get("geometry") or {}
            geom_type = geom.get("type", "")
            coords = geom.get("coordinates")
            row: dict[str, Any] = {"_geom_type": geom_type, **props}
            if coords is not None:
                row["_coordinates"] = json.dumps(coords)
                lon, lat = _centroid(coords, geom_type)
                if lat is not None:
                    row["_lat"] = str(round(lat, 7))
                    row["_lon"] = str(round(lon, 7))  # type: ignore[arg-type]
            rows.append(row)
        return rows

    @staticmethod
    def _parse_gml(xml_text: str) -> list[dict[str, Any]]:
        """Very basic GML→rows parser for fallback coverage."""
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return rows
        # Iterate member elements
        for member in root.iter():
            tag = member.tag.split("}")[-1] if "}" in member.tag else member.tag
            if tag not in ("member", "featureMember", "featureMembers"):
                continue
            for feature in member:
                row: dict[str, Any] = {}
                for child in feature:
                    local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if child.text and child.text.strip():
                        row[local] = child.text.strip()
                    # Extract GML Point coordinates
                    for pos in child.iter():
                        ptag = pos.tag.split("}")[-1] if "}" in pos.tag else pos.tag
                        if ptag in ("pos", "coordinates") and pos.text:
                            parts = pos.text.strip().split()
                            if len(parts) >= 2:
                                try:
                                    lon = float(parts[0])
                                    lat = float(parts[1])
                                    row["_lon"] = str(lon)
                                    row["_lat"] = str(lat)
                                    row["_geom_type"] = "Point"
                                    # Store as GeoJSON Point coordinates for consistent rendering
                                    row["_coordinates"] = json.dumps([lon, lat])
                                except ValueError:
                                    pass
                if row:
                    rows.append(row)
        return rows
