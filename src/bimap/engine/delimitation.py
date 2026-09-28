"""Delimitation engine — fetch administrative boundary polygons from Nominatim."""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

from bimap.config import HTTP_HEADERS, NOMINATIM_URL


@dataclass
class DelimitationResult:
    name: str
    lat: float
    lon: float
    # Outer ring as [[lon, lat], ...] (GeoJSON coordinate order)
    polygon: list[list[float]] | None = None
    # (min_lat, max_lat, min_lon, max_lon)
    bbox: tuple[float, float, float, float] | None = None

    def bbox_polygon(self) -> list[list[float]] | None:
        """Return the bounding box as a closed polygon [[lon, lat], ...] if no real polygon."""
        if self.bbox is None:
            return None
        min_lat, max_lat, min_lon, max_lon = self.bbox
        return [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat],
        ]


def fetch_places_with_polygon(query: str, limit: int = 8) -> list[DelimitationResult]:
    """
    Search Nominatim for *query* and return results with boundary polygon data.

    Requests ``polygon_geojson=1`` so Nominatim attaches a GeoJSON geometry to
    each result when one is available in OSM.
    """
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": limit,
                "polygon_geojson": 1,
            },
            headers={**HTTP_HEADERS, "Accept-Language": "en"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return []

    results: list[DelimitationResult] = []
    for item in resp.json():
        try:
            geojson = item.get("geojson") or {}
            polygon = _extract_outer_ring(geojson)
            bb = item.get("boundingbox")  # [min_lat, max_lat, min_lon, max_lon]
            bbox: tuple[float, float, float, float] | None = (
                (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])) if bb else None
            )
            results.append(
                DelimitationResult(
                    name=item["display_name"],
                    lat=float(item["lat"]),
                    lon=float(item["lon"]),
                    polygon=polygon,
                    bbox=bbox,
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return results


def _extract_outer_ring(geojson: dict) -> list[list[float]] | None:
    """Extract the outer ring [[lon, lat], ...] from a GeoJSON Polygon or MultiPolygon."""
    gtype = geojson.get("type", "")
    coords = geojson.get("coordinates")
    if not coords:
        return None
    if gtype == "Polygon":
        return coords[0]
    if gtype == "MultiPolygon":
        rings = [poly[0] for poly in coords if poly]
        return max(rings, key=len) if rings else None
    return None
