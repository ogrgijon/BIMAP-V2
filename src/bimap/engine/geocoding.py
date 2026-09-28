"""Geocoding service using Nominatim (OpenStreetMap)."""

from __future__ import annotations

from dataclasses import dataclass

import requests
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot

from bimap.config import HTTP_HEADERS, NOMINATIM_URL


@dataclass
class GeoResult:
    display_name: str
    lat: float
    lon: float
    bbox: tuple[float, float, float, float] | None  # (south, north, west, east)


def geocode(query: str, limit: int = 8) -> list[GeoResult]:
    """
    Search for *query* via Nominatim and return up to *limit* results.
    Returns an empty list on network/parse errors (caller should show a message).
    """
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": limit,
                "addressdetails": 0,
            },
            headers={**HTTP_HEADERS, "Accept-Language": "en"},
            timeout=8,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return []

    results: list[GeoResult] = []
    for item in resp.json():
        try:
            bb = item.get("boundingbox")  # [min_lat, max_lat, min_lon, max_lon]
            bbox = (
                float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
            ) if bb else None
            results.append(
                GeoResult(
                    display_name=item["display_name"],
                    lat=float(item["lat"]),
                    lon=float(item["lon"]),
                    bbox=bbox,
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return results


class _GeoWorkerSignals(QObject):
    result = pyqtSignal(object)       # GeoResult | None
    error = pyqtSignal(str)


class GeocoderWorker(QRunnable):
    """Run a geocode query on Qt's global thread pool (non-blocking)."""

    def __init__(self, query: str) -> None:
        super().__init__()
        self.signals = _GeoWorkerSignals()
        self._query = query
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self) -> None:
        results = geocode(self._query, limit=1)
        if results:
            self.signals.result.emit(results[0])
        else:
            self.signals.error.emit(f"No results for '{self._query}'")
