"""Data source configuration and field mapping models."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    CSV = "csv"
    EXCEL = "excel"
    SQL = "sql"
    REST_API = "rest_api"
    GOOGLE_SHEETS = "gsheets"
    GEOJSON = "geojson"
    WFS = "wfs"
    WMS = "wms"


class RefreshMode(StrEnum):
    MANUAL = "manual"
    ON_OPEN = "on_open"
    INTERVAL = "interval"


class FieldMapping(BaseModel):
    source_column: str
    target_element_type: str    # "zone" | "keypoint"
    target_element_id: str      # UUID str of the element
    target_property: str        # e.g. "style.fill_color"
    transform: str = ""         # optional expression; 'value' = source value


class DataSource(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = "Data Source"
    source_type: SourceType = SourceType.CSV
    # Type-specific connection params (path, url, query, auth, etc.)
    connection: dict[str, str] = Field(default_factory=dict)
    refresh_mode: RefreshMode = RefreshMode.MANUAL
    refresh_interval_sec: int = 300
    field_mappings: list[FieldMapping] = Field(default_factory=list)
    last_refresh: str = ""      # ISO datetime string
    last_error: str = ""
    enabled: bool = True
    # Geographic extent [min_lat, min_lon, max_lat, max_lon] — derived from data/capabilities
    extent: list[float] = Field(default_factory=list)
    # Runtime status — not persisted (excluded from serialisation)
    connection_state: str = ""  # "" | "connecting" | "ok" | "error"
    row_count: int = 0
    last_refresh_ms: int = 0    # duration of last successful fetch in ms
