"""Data source package — factory function."""

from __future__ import annotations

from typing import Any

from bimap.data.api_source import ApiSource
from bimap.data.base import DataSourceBase
from bimap.data.csv_source import CsvSource
from bimap.data.geojson_source import GeoJsonSource
from bimap.data.refresh import DataRefreshManager, RefreshWorker
from bimap.data.sql_source import SqlSource
from bimap.data.wfs_source import WfsSource
from bimap.data.wms_source import WmsSource
from bimap.models.data_source import DataSource, SourceType


def build_connector(ds: DataSource) -> DataSourceBase:
    """Factory: create the appropriate connector from a DataSource model."""
    c = ds.connection
    match ds.source_type:
        case SourceType.CSV | SourceType.EXCEL:
            return CsvSource(
                file_path=c.get("file_path", ""),
                sheet_name=c.get("sheet_name", 0),
            )
        case SourceType.SQL:
            from bimap.secrets import get_secret
            conn_str = get_secret(f"datasource_{str(ds.id)}") or c.get("connection_string", "")
            return SqlSource(
                connection_string=conn_str,
                query=c.get("query", "SELECT 1"),
            )
        case SourceType.REST_API:
            return ApiSource(
                url=c.get("url", ""),
                data_path=c.get("data_path", ""),
                auth_token=c.get("auth_token", ""),
            )
        case SourceType.GEOJSON:
            return GeoJsonSource(path_or_url=c.get("path_or_url", ""))
        case SourceType.WFS:
            return WfsSource(
                url=c.get("url", ""),
                type_name=c.get("type_name", ""),
                max_features=int(c.get("max_features", 500) or 500),
                bbox=c.get("bbox", ""),
                cql_filter=c.get("cql_filter", ""),
            )
        case SourceType.WMS:
            return WmsSource(
                url=c.get("url", ""),
                layer_name=c.get("layer_name", ""),
                styles=c.get("styles", ""),
                bbox=c.get("bbox", ""),
                info_format=c.get("info_format", "application/json"),
                width=int(c.get("width", 101) or 101),
                height=int(c.get("height", 101) or 101),
            )
        case SourceType.GOOGLE_SHEETS:
            raise NotImplementedError(
                "Google Sheets connector is not yet implemented. "
                "Use a REST API source with the Sheets JSON export URL instead."
            )
        case _:
            raise ValueError(f"Unsupported source type: {ds.source_type}")


__all__ = [
    "ApiSource",
    "CsvSource",
    "DataRefreshManager",
    "DataSourceBase",
    "GeoJsonSource",
    "RefreshWorker",
    "SqlSource",
    "WfsSource",
    "WmsSource",
    "build_connector",
]
