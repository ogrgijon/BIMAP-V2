"""Map viewport state model."""

from __future__ import annotations

from pydantic import BaseModel, Field

from bimap.config import (
    DEFAULT_CENTER_LAT,
    DEFAULT_CENTER_LON,
    DEFAULT_TILE_PROVIDER,
    DEFAULT_ZOOM,
)


class ViewportBookmark(BaseModel):
    name: str
    lat: float
    lon: float
    zoom: int


class MapState(BaseModel):
    center_lat: float = DEFAULT_CENTER_LAT
    center_lon: float = DEFAULT_CENTER_LON
    zoom: int = Field(default=DEFAULT_ZOOM, ge=1, le=21)
    rotation: float = 0.0
    tile_provider: str = DEFAULT_TILE_PROVIDER
    bookmarks: list[ViewportBookmark] = Field(default_factory=list)
    # Active delimitation boundary
    delimitation_name: str = ""
    delimitation_polygon: list[list[float]] | None = None  # [[lon, lat], ...] outer ring
