"""Style primitives shared across all map elements."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class BorderStyle(StrEnum):
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class HatchPattern(StrEnum):
    NONE = "none"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    DIAGONAL = "diagonal"
    CROSSHATCH = "crosshatch"


class ZoneStyle(BaseModel):
    fill_color: str = "#3388FF"
    fill_alpha: int = Field(default=80, ge=0, le=255)
    border_color: str = "#1A60CC"
    border_width: int = Field(default=2, ge=0, le=20)
    border_style: BorderStyle = BorderStyle.SOLID
    hatch: HatchPattern = HatchPattern.NONE


class LabelStyle(BaseModel):
    font_family: str = "Arial"
    font_size: int = Field(default=11, ge=6, le=72)
    bold: bool = False
    italic: bool = False
    color: str = "#222222"
    background_color: str | None = None
    padding: int = 4


class ZoneLabel(BaseModel):
    text: str = ""
    style: LabelStyle = Field(default_factory=LabelStyle)
    auto_position: bool = True
    offset_x: float = 0.0
    offset_y: float = 0.0


class AnnotationStyle(BaseModel):
    font_family: str = "Arial"
    font_size: int = Field(default=12, ge=6, le=72)
    bold: bool = False
    italic: bool = False
    color: str = "#222222"
    background_color: str = "#FFFFFF"
    background_alpha: int = Field(default=230, ge=0, le=255)
    border_color: str = "#AAAAAA"
    border_width: int = Field(default=1, ge=0, le=10)
    padding: int = 6


class StylePreset(BaseModel):
    name: str
    zone_style: ZoneStyle = Field(default_factory=ZoneStyle)
    label_style: LabelStyle = Field(default_factory=LabelStyle)
