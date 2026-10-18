"""GeoPackage data source connector."""

from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path
from typing import Any

from bimap.data.base import DataSourceBase


class GeoPackageSource(DataSourceBase):
    """Reads the first feature table from a GeoPackage."""

    def __init__(self, file_path: str, table_name: str = "") -> None:
        self._path = Path(file_path)
        self._table_name = table_name
        self._rows: list[dict[str, Any]] = []
        self._columns: list[str] = []

    def connect(self) -> None:
        if not self._path.exists():
            raise ValueError(f"GeoPackage not found: {self._path}")

    def fetch(self) -> list[dict[str, Any]]:
        db = sqlite3.connect(self._path)
        try:
            table = self._table_name
            if not table:
                row = db.execute(
                    "SELECT table_name FROM gpkg_contents WHERE data_type = 'features' "
                    "ORDER BY table_name LIMIT 1"
                ).fetchone()
                if not row:
                    raise ValueError("GeoPackage contains no feature tables.")
                table = str(row[0])
            safe_table = '"' + table.replace('"', '""') + '"'
            columns = [d[0] for d in db.execute(f"SELECT * FROM {safe_table} LIMIT 0").description]
            geom_column = db.execute(
                "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
                (table,),
            ).fetchone()
            geom_name = geom_column[0] if geom_column else "geom"
            self._rows = []
            for values in db.execute(f"SELECT * FROM {safe_table}"):
                row = dict(zip(columns, values))
                geometry = row.pop(geom_name, None)
                if geometry:
                    coords, geom_type = _decode_geometry(geometry)
                    row["_geom_type"] = geom_type
                    row["_coordinates"] = json.dumps(coords)
                    if geom_type == "Point":
                        row["_lon"], row["_lat"] = str(coords[0]), str(coords[1])
                self._rows.append(row)
            self._columns = list(self._rows[0]) if self._rows else [c for c in columns if c != geom_name]
        finally:
            db.close()
        return self._rows

    def get_columns(self) -> list[str]:
        return self._columns

    def disconnect(self) -> None:
        self._rows = []
        self._columns = []


def _decode_geometry(blob: bytes) -> tuple[Any, str]:
    if blob[:2] == b"GP":
        flags = blob[3]
        envelope = (flags >> 1) & 7
        offset = 8 + {0: 0, 1: 32, 2: 48, 3: 48}[envelope]
        blob = blob[offset:]
    endian = "<" if blob[0] == 1 else ">"
    geom_type = struct.unpack_from(endian + "I", blob, 1)[0]
    name = {1: "Point", 2: "LineString", 3: "Polygon"}.get(geom_type, "Geometry")
    if geom_type == 1:
        return struct.unpack_from(endian + "2d", blob, 5), name
    count = struct.unpack_from(endian + "I", blob, 5)[0]
    points = [struct.unpack_from(endian + "2d", blob, 9 + i * 16) for i in range(count)]
    return points, name
