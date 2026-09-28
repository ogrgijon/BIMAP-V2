"""Zone (polygon/shape) domain model."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from bimap.models.style import ZoneLabel, ZoneStyle


class ZoneType(StrEnum):
    POLYGON = "polygon"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"


class LatLon(BaseModel):
    lat: float
    lon: float


class DataBinding(BaseModel):
    """Link a data-source column to a zone/keypoint property."""
    source_id: str           # UUID str of the DataSource
    column: str              # column/field name in the source
    target_property: str     # e.g. "style.fill_color", "info_card.revenue"
    transform: str = ""      # optional Python expression, 'value' is the variable


class MetadataKeyBinding(BaseModel):
    """Link a metadata key's value to a column in a registered DataSource.

    When the data source refreshes, BIMAP resolves the bound rows and
    overwrites the metadata key with the aggregated column value.
    """
    source_id: str              # UUID str of the DataSource
    column: str                 # source column whose value to use
    match_field: str = ""       # source field used for row filtering (empty = all rows)
    match_value: str = "{{element.name}}"  # literal or {{element.name}} / {{element.id}}
    aggregate: str = "first"    # "first" | "last" | "sum" | "avg" | "count"


class Zone(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = "Zone"
    zone_type: ZoneType = ZoneType.POLYGON
    # For polygon/rectangle/freehand: list of vertices.
    # For circle: [center] and radius_m field.
    coordinates: list[LatLon] = Field(default_factory=list)
    radius_m: float = 500.0              # only used for ZoneType.CIRCLE
    group: str = "Default"
    visible: bool = True
    style: ZoneStyle = Field(default_factory=ZoneStyle)
    label: ZoneLabel = Field(default_factory=ZoneLabel)
    data_binding: DataBinding | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    metadata_hidden: list[str] = Field(default_factory=list)           # keys hidden from BIMAP_DATA
    metadata_bindings: dict[str, MetadataKeyBinding] = Field(default_factory=dict)  # key → source binding
    locked: bool = False              # locked zones cannot be selected/moved
    layer: str = "Default"
    extension_html: str = ""         # optional HTML5/CSS/JS viewer extension
    extension_name: str = ""         # display name of the assigned extension
    # ── Geometry overrides ──────────────────────────────────────────────────── #
    width_m: float = 0.0             # rectangle: explicit width in metres (0 = use vertices)
    height_m: float = 0.0            # rectangle: explicit height in metres (0 = use vertices)
    # ── SVG fill ─────────────────────────────────────────────────────────────── #
    svg_fill_url: str = ""           # path to an .svg file rendered as zone fill
    # ── Rotation ─────────────────────────────────────────────────────────────── #
    rotation_deg: float = 0.0        # clockwise rotation in degrees (0 = no rotation)
    # ── Associated form design ───────────────────────────────────────────────── #
    form_design_id: str = ""         # UUID str of the FormDesign linked to this zone
