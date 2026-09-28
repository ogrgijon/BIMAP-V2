"""Live feed layer models — real-time position data."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class LiveMarker(BaseModel):
    """A single position record received from a live feed."""

    id: str
    lat: float
    lon: float
    label: str = ""
    speed: float | None = None      # km/h, optional
    heading: float | None = None    # 0–360°, optional
    extra: dict[str, Any] = Field(default_factory=dict)


class LiveLayer(BaseModel):
    """Configuration for a real-time position feed layer."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    feed_url: str                   # REST endpoint returning JSON positions
    poll_interval_ms: int = 5000
    lat_field: str = "lat"
    lon_field: str = "lon"
    label_field: str = "id"
    icon: str = "▶"                 # Unicode glyph or "dot"
    icon_color: str = "#00d4ff"
    icon_size: int = 14
    visible: bool = True
    trail_length: int = 0           # 0 = no trail; N = keep last N positions per marker
    auth_header: str = ""           # e.g. "Authorization: Bearer <token>"
