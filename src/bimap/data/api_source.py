"""REST API data source connector."""

from __future__ import annotations

from typing import Any

import requests

from bimap.config import HTTP_HEADERS
from bimap.data.base import DataSourceBase
from bimap.engine._utils import get_nested


class ApiSource(DataSourceBase):
    """Fetches JSON from a REST endpoint and flattens a list of records."""

    def __init__(
        self,
        url: str,
        data_path: str = "",        # dot-path to the list within the JSON
        headers: dict[str, str] | None = None,
        auth_token: str = "",
        params: dict[str, str] | None = None,
    ) -> None:
        self._url = url
        self._data_path = data_path
        self._headers = {**HTTP_HEADERS, **(headers or {})}
        if auth_token:
            self._headers["Authorization"] = f"Bearer {auth_token}"
        self._params = params or {}
        self._columns: list[str] = []

    def connect(self) -> None:
        if not self._url.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")

    def fetch(self) -> list[dict[str, Any]]:
        try:
            resp = requests.get(self._url, headers=self._headers,
                                params=self._params, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            raise ValueError(f"API request failed: {exc}") from exc

        if self._data_path:
            payload = get_nested(payload, self._data_path)

        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []

        rows: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                rows.append(item)
        if rows:
            self._columns = list(rows[0].keys())
        return rows

    def get_columns(self) -> list[str]:
        return self._columns

    def disconnect(self) -> None:
        pass
