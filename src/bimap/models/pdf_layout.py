"""PDF layout model for the print composer."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PageOrientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class LayoutItemType(StrEnum):
    MAP_FRAME = "map_frame"
    TITLE_BLOCK = "title_block"
    LEGEND = "legend"
    KEYNOTE_TABLE = "keynote_table"
    TEXT_BLOCK = "text_block"
    IMAGE = "image"
    SCALE_BAR = "scale_bar"
    NORTH_ARROW = "north_arrow"


class LayoutRect(BaseModel):
    x: float = 50.0      # points from left
    y: float = 50.0      # points from top
    width: float = 400.0
    height: float = 300.0


class LayoutItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    item_type: LayoutItemType = LayoutItemType.MAP_FRAME
    rect: LayoutRect = Field(default_factory=LayoutRect)
    content: dict[str, str] = Field(default_factory=dict)
    # For MAP_FRAME: viewport snapshot
    map_center_lat: float | None = None
    map_center_lon: float | None = None
    map_zoom: int | None = None
    z_order: int = 0
    visible: bool = True


class PDFLayout(BaseModel):
    page_size: str = "A4"       # key from config.PDF_PAGE_SIZES
    orientation: PageOrientation = PageOrientation.LANDSCAPE
    dpi: int = 300
    margin: float = 36.0       # points (0.5 inch)
    items: list[LayoutItem] = Field(default_factory=list)
    # Composer options
    capture_zoom: int | None = None   # None = use the current map zoom
    show_legend: bool = True
    legend_title: str = "Legend"
    legend_hidden_layers: list[str] = Field(default_factory=list)
    legend_custom_labels: dict[str, str] = Field(default_factory=dict)
    show_info_box: bool = False
    info_box_title: str = ""
    info_box_author: str = ""
    info_box_date: str = ""
    info_box_text: str = ""  # multi-line free text block (used instead of title when non-empty)
    # Architectural title block fields
    tb_enabled: bool = True     # show/hide the entire title block strip
    tb_project_name: str = ""   # override name (blank → use project.name at render time)
    tb_drawn_by: str = ""
    tb_checked_by: str = ""
    tb_revision: str = "A"
    tb_scale: str = "1:NTS"
    tb_sheet: str = "1 / 1"
    tb_description: str = ""   # project description / subtitle shown in middle column
