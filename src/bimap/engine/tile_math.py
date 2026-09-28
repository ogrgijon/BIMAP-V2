"""Web Mercator (EPSG:3857) tile math — pure Python, no external projection lib."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NamedTuple

from bimap.config import TILE_SIZE


@dataclass(frozen=True)
class TileCoord:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class PixelCoord:
    px: float
    py: float


class TileFloatCoord(NamedTuple):
    """Fractional tile coordinates — supports tuple unpacking and attribute access."""
    x: float
    y: float


class LatLonCoord(NamedTuple):
    """Latitude/longitude point — supports tuple unpacking and attribute access."""
    lat: float
    lon: float


# ── Core conversions ──────────────────────────────────────────────────────────

def lat_lon_to_tile_float(lat: float, lon: float, zoom: int) -> TileFloatCoord:
    """Return fractional tile coordinates (tx, ty) for given lat/lon/zoom."""
    n = 2.0 ** zoom
    tx = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    ty = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return TileFloatCoord(tx, ty)


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> TileCoord:
    """Return integer tile (x, y, z) for the tile containing lat/lon."""
    tx, ty = lat_lon_to_tile_float(lat, lon, zoom)
    return TileCoord(x=int(tx), y=int(ty), z=zoom)


def tile_to_lat_lon(x: int, y: int, zoom: int) -> LatLonCoord:
    """Return lat/lon of the top-left corner of tile (x, y, z)."""
    n = 2.0 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n)))
    lat = math.degrees(lat_rad)
    return LatLonCoord(lat, lon)


def lat_lon_to_pixel(
    lat: float,
    lon: float,
    center_lat: float,
    center_lon: float,
    zoom: int,
    widget_w: int,
    widget_h: int,
) -> PixelCoord:
    """Convert a lat/lon point to pixel coordinates in the map widget."""
    cx, cy = lat_lon_to_tile_float(center_lat, center_lon, zoom)
    px_f, py_f = lat_lon_to_tile_float(lat, lon, zoom)
    dx = (px_f - cx) * TILE_SIZE
    dy = (py_f - cy) * TILE_SIZE
    return PixelCoord(px=widget_w / 2.0 + dx, py=widget_h / 2.0 + dy)


def pixel_to_lat_lon(
    px: float,
    py: float,
    center_lat: float,
    center_lon: float,
    zoom: int,
    widget_w: int,
    widget_h: int,
) -> tuple[float, float]:
    """Convert pixel coords in the map widget to lat/lon."""
    cx, cy = lat_lon_to_tile_float(center_lat, center_lon, zoom)
    tx = cx + (px - widget_w / 2.0) / TILE_SIZE
    ty = cy + (py - widget_h / 2.0) / TILE_SIZE
    # Invert ty -> lat
    n = 2.0 ** zoom
    lon = tx / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * ty / n)))
    lat = math.degrees(lat_rad)
    return lat, lon


# ── Viewport helpers ──────────────────────────────────────────────────────────

def visible_tiles(
    center_lat: float,
    center_lon: float,
    zoom: int,
    widget_w: int,
    widget_h: int,
) -> list[tuple[TileCoord, int, int]]:
    """
    Return list of (TileCoord, pixel_x, pixel_y) for all tiles visible
    in the widget.  pixel_x/y is the top-left corner of the tile in
    widget-pixel space.
    """
    cx, cy = lat_lon_to_tile_float(center_lat, center_lon, zoom)
    # Integer tile under centre + fractional offset
    cx_int = int(cx)
    cy_int = int(cy)
    cx_frac = cx - cx_int   # in [0..1)
    cy_frac = cy - cy_int

    # Pixel coord of top-left of the centre tile
    origin_x = int(widget_w / 2 - cx_frac * TILE_SIZE)
    origin_y = int(widget_h / 2 - cy_frac * TILE_SIZE)

    tiles_x = math.ceil(widget_w / TILE_SIZE) + 2
    tiles_y = math.ceil(widget_h / TILE_SIZE) + 2

    half_x = tiles_x // 2
    half_y = tiles_y // 2

    max_tile = 2 ** zoom
    result: list[tuple[TileCoord, int, int]] = []
    for dy in range(-half_y, half_y + 1):
        for dx in range(-half_x, half_x + 1):
            tx = (cx_int + dx) % max_tile
            ty = cy_int + dy
            if ty < 0 or ty >= max_tile:
                continue
            px = origin_x + dx * TILE_SIZE
            py = origin_y + dy * TILE_SIZE
            # Cull tiles entirely outside viewport
            if px + TILE_SIZE < 0 or px > widget_w:
                continue
            if py + TILE_SIZE < 0 or py > widget_h:
                continue
            result.append((TileCoord(x=tx, y=ty, z=zoom), px, py))
    return result


def meters_per_pixel(lat: float, zoom: int) -> float:
    """Ground resolution in metres per pixel at the given latitude and zoom."""
    return (math.cos(math.radians(lat)) * 2 * math.pi * 6_378_137) / (TILE_SIZE * 2 ** zoom)
