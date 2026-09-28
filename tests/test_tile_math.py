"""
Tests for engine/tile_math.py — pure math, no Qt needed.
"""

from __future__ import annotations

import math
import pytest

from bimap.engine.tile_math import (
    lat_lon_to_tile,
    lat_lon_to_tile_float,
    tile_to_lat_lon,
    lat_lon_to_pixel,
    pixel_to_lat_lon,
    meters_per_pixel,
    visible_tiles,
)


class TestLatLonToTile:
    def test_known_tile_zoom0(self):
        t = lat_lon_to_tile(0.0, 0.0, 0)
        assert t.x == 0
        assert t.y == 0
        assert t.z == 0

    def test_madrid_zoom12(self):
        t = lat_lon_to_tile(40.4168, -3.7038, 12)
        # Madrid at zoom 12 is around tile (2008, 1546)
        assert 2000 <= t.x <= 2020
        assert 1535 <= t.y <= 1560
        assert t.z == 12

    def test_equator_dateline_symmetry(self):
        east = lat_lon_to_tile_float(0.0, 90.0, 2)
        west = lat_lon_to_tile_float(0.0, -90.0, 2)
        mid  = lat_lon_to_tile_float(0.0, 0.0, 2)
        # lat_lon_to_tile_float returns (x, y) as a plain tuple
        assert east[0] > mid[0]
        assert west[0] < mid[0]


class TestTileRoundTrip:
    @pytest.mark.parametrize("lat,lon,zoom", [
        (40.4168, -3.7038, 10),
        (51.5074, -0.1278, 14),
        (-33.8688, 151.2093, 12),
        (0.0, 0.0, 8),
    ])
    def test_lat_lon_tile_roundtrip(self, lat, lon, zoom):
        """lat/lon → tile_float → lat/lon should be within tile resolution."""
        tx, ty = lat_lon_to_tile_float(lat, lon, zoom)
        rec_lat, rec_lon = tile_to_lat_lon(tx, ty, zoom)
        # Acceptable error depends on tile resolution
        tolerance = 360.0 / (256 * 2 ** zoom) * 10
        assert abs(rec_lat - lat) < tolerance
        assert abs(rec_lon - lon) < tolerance


class TestPixelConversions:
    def test_center_maps_to_half_width(self):
        lat, lon, zoom = 40.0, -3.0, 12
        w, h = 800, 600
        p = lat_lon_to_pixel(lat, lon, lat, lon, zoom, w, h)
        assert abs(p.px - w / 2) < 1.0
        assert abs(p.py - h / 2) < 1.0

    def test_pixel_roundtrip(self):
        lat, lon, zoom = 48.8566, 2.3522, 13
        w, h = 1024, 768
        p = lat_lon_to_pixel(lat, lon, lat, lon, zoom, w, h)
        recovered = pixel_to_lat_lon(p.px, p.py, lat, lon, zoom, w, h)
        assert abs(recovered[0] - lat) < 1e-6
        assert abs(recovered[1] - lon) < 1e-6


class TestMetersPerPixel:
    def test_equator_is_largest(self):
        mpp_equator = meters_per_pixel(0.0, 10)
        mpp_arctic  = meters_per_pixel(70.0, 10)
        assert mpp_equator > mpp_arctic

    def test_zoom_doubles_resolution(self):
        mpp_z10 = meters_per_pixel(0.0, 10)
        mpp_z11 = meters_per_pixel(0.0, 11)
        assert abs(mpp_z10 / mpp_z11 - 2.0) < 0.01


class TestVisibleTiles:
    def test_returns_list(self):
        tiles = visible_tiles(40.4, -3.7, 10, 800, 600)
        assert isinstance(tiles, list)
        assert len(tiles) > 0

    def test_tile_structure(self):
        tiles = visible_tiles(40.4, -3.7, 10, 800, 600)
        coord, px, py = tiles[0]
        assert hasattr(coord, 'x')
        assert hasattr(coord, 'y')
        assert hasattr(coord, 'z')
        assert isinstance(px, (int, float))
        assert isinstance(py, (int, float))
