"""Form design domain model.

A ``FormDesign`` describes a set of typed fields that can be associated with
a zone or keypoint.  When the user fills in the form, each field value is
stored as a metadata key on the element (key = field label, value = entered
value).
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FieldType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    DATE = "date"
    TEXTAREA = "textarea"


class FormField(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    label: str = "Field"
    field_type: FieldType = FieldType.TEXT
    options: list[str] = Field(default_factory=list)   # used by DROPDOWN
    required: bool = False
    default_value: str = ""


class FormDesign(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = "My Form"
    description: str = ""
    # "zone", "keypoint", or "both"
    target: str = "both"
    fields: list[FormField] = Field(default_factory=list)
