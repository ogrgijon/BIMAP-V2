"""GeoJSON file or URL data source connector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from bimap.config import HTTP_HEADERS
from bimap.data.base import DataSourceBase


def _centroid(coords: Any, geom_type: str) -> tuple[float | None, float | None]:
    """Return (lon, lat) centroid from a GeoJSON coordinate array."""
    try:
        if geom_type == "Point":
            return float(coords[0]), float(coords[1])
        if geom_type in ("LineString", "MultiPoint"):
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            return sum(lons) / len(lons), sum(lats) / len(lats)
        if geom_type == "Polygon":
            ring = coords[0]
            lons = [c[0] for c in ring]
            lats = [c[1] for c in ring]
            return sum(lons) / len(lons), sum(lats) / len(lats)
        if geom_type in ("MultiPolygon", "MultiLineString"):
            ring = coords[0][0]
            lons = [c[0] for c in ring]
            lats = [c[1] for c in ring]
            return sum(lons) / len(lons), sum(lats) / len(lats)
    except (TypeError, IndexError, ZeroDivisionError):
        pass
    return None, None


class GeoJsonSource(DataSourceBase):
    """Reads GeoJSON from a local file or remote URL."""

    def __init__(self, path_or_url: str) -> None:
        self._src = path_or_url
        self._rows: list[dict[str, Any]] = []
        self._columns: list[str] = []
        self._extent: list[float] = []  # [min_lat, min_lon, max_lat, max_lon]

    def connect(self) -> None:
        if not (self._src.startswith("http") or Path(self._src).exists()):
            raise ValueError(f"GeoJSON source not found: {self._src}")

    def fetch(self) -> list[dict[str, Any]]:
        if self._src.startswith("http"):
            try:
                resp = requests.get(self._src, headers=HTTP_HEADERS, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                raise ValueError(f"GeoJSON fetch failed: {exc}") from exc
        else:
            data = json.loads(Path(self._src).read_text(encoding="utf-8"))

        features = data.get("features", [])
        rows = []
        for f in features:
            props = f.get("properties") or {}
            geom = f.get("geometry") or {}
            geom_type = geom.get("type", "")
            row: dict[str, Any] = {"_geom_type": geom_type, **props}
            coords = geom.get("coordinates")
            if coords is not None:
                row["_coordinates"] = json.dumps(coords)
                lon, lat = _centroid(coords, geom_type)
                if lat is not None:
                    row["_lat"] = str(round(lat, 7))
                    row["_lon"] = str(round(lon, 7))  # type: ignore[arg-type]
            rows.append(row)
        self._rows = rows
        if rows:
            self._columns = list(rows[0].keys())
            lats = [float(r["_lat"]) for r in rows if r.get("_lat")]
            lons = [float(r["_lon"]) for r in rows if r.get("_lon")]
            if lats:
                self._extent = [min(lats), min(lons), max(lats), max(lons)]
        return rows

    def get_columns(self) -> list[str]:
        return self._columns

    def get_extent(self) -> list[float] | None:
        return self._extent if self._extent else None

    def disconnect(self) -> None:
        self._rows = []
        self._columns = []
