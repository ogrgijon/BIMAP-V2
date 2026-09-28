"""Layer domain model."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Layer(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = "Default"
    visible: bool = True
    color: str = "#888888"
    key_library: list[str] = Field(default_factory=list)
