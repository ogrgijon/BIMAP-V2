"""DataLayer model — a visual overlay driven by a DataSource."""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field


class DataLayer(BaseModel):
    """Visual overlay that renders rows fetched by a registered DataSource.

    Created automatically when a DataSource is added.  Any row that contains
    ``_lat``/``_lon`` is drawn as a dot; rows with ``_coordinates`` +
    ``_geom_type`` are drawn as points, lines, or polygons.  Rows with no
    geographic fields are silently skipped.

    Attributes
    ----------
    id:
        Stable UUID string for this data layer.
    name:
        Display name shown in the Layers panel.
    source_id:
        UUID string of the linked :class:`~bimap.models.data_source.DataSource`.
    visible:
        Whether the layer is currently shown on the canvas.
    opacity:
        Layer transparency (0.0 = fully transparent, 1.0 = fully opaque).
    icon_color:
        Hex colour used for dots, lines and polygon strokes.
    icon_size:
        Radius (px) of point markers; line/stroke width scales with it.
    label_column:
        Optional column name whose value is drawn next to each point marker.
        Leave blank to draw no labels.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Data Layer"
    source_id: str = ""            # UUID str of the linked DataSource
    visible: bool = True
    opacity: float = 1.0           # layer opacity (0.0 = transparent, 1.0 = opaque)
    icon_color: str = "#3b82f6"    # blue
    icon_size: int = 10
    label_column: str = ""         # column to use as map label (optional)
