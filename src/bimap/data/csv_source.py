"""CSV and Excel data source connector."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from bimap.data.base import DataSourceBase


class CsvSource(DataSourceBase):
    """Reads a CSV or Excel file and returns rows as dicts."""

    def __init__(self, file_path: str, sheet_name: str | int = 0) -> None:
        self._path = Path(file_path)
        self._sheet_name = sheet_name
        self._rows: list[dict[str, Any]] = []
        self._columns: list[str] = []

    def connect(self) -> None:
        if not self._path.exists():
            raise ValueError(f"File not found: {self._path}")

    def fetch(self) -> list[dict[str, Any]]:
        suffix = self._path.suffix.lower()
        if suffix in (".xls", ".xlsx", ".xlsm"):
            self._rows = self._read_excel()
        else:
            self._rows = self._read_csv()
        if self._rows:
            self._columns = list(self._rows[0].keys())
        return self._rows

    def _read_csv(self) -> list[dict[str, Any]]:
        rows = []
        with self._path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(dict(row))
        return rows

    def _read_excel(self) -> list[dict[str, Any]]:
        try:
            import openpyxl
        except ImportError as exc:
            raise ValueError("openpyxl is required to read Excel files.") from exc
        wb = openpyxl.load_workbook(self._path, read_only=True, data_only=True)
        if isinstance(self._sheet_name, int):
            ws = wb.worksheets[self._sheet_name]
        else:
            ws = wb[self._sheet_name]
        rows_iter = iter(ws.iter_rows(values_only=True))
        headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(next(rows_iter, []))]
        rows = []
        for row in rows_iter:
            rows.append({h: v for h, v in zip(headers, row)})
        wb.close()
        return rows

    def get_columns(self) -> list[str]:
        return self._columns

    def disconnect(self) -> None:
        self._rows = []
        self._columns = []
