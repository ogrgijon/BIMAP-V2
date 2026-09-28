"""Abstract data source interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DataSourceBase(ABC):
    """All data source connectors must implement this interface."""

    @abstractmethod
    def connect(self) -> None:
        """Validate/open the connection.  Raise ValueError on failure."""

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Fetch and return data as a list of row dicts."""

    @abstractmethod
    def get_columns(self) -> list[str]:
        """Return column/field names available in this source."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release resources."""

    def get_extent(self) -> list[float] | None:
        """Return [min_lat, min_lon, max_lat, max_lon] if known, else None.

        Override in connectors that can derive a geographic extent from their
        metadata (e.g. WFS GetCapabilities) or fetched data.
        """
        return None
