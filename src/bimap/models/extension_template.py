"""Extension template model for the MerekaiBIMAP extension library."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ExtensionTemplate(BaseModel):
    """A named, reusable HTML5/CSS/JS extension stored in the project library."""

    id: UUID = Field(default_factory=uuid4)
    name: str = "My Extension"
    description: str = ""
    html: str = ""         # full HTML5 document (MerekaiBIMAP_DATA is injected at runtime)
