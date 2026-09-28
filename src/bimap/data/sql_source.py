"""SQL database data source connector (via SQLAlchemy)."""

from __future__ import annotations

from typing import Any

from bimap.data.base import DataSourceBase


class SqlSource(DataSourceBase):
    """Executes a SELECT query against any SQLAlchemy-supported database."""

    def __init__(self, connection_string: str, query: str) -> None:
        self._conn_str = connection_string
        self._query = query
        self._engine = None
        self._columns: list[str] = []

    def connect(self) -> None:
        try:
            from sqlalchemy import create_engine, text
            self._engine = create_engine(self._conn_str)
            # Verify connectivity
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            raise ValueError(f"DB connection failed: {exc}") from exc

    def fetch(self) -> list[dict[str, Any]]:
        q = self._query.strip()
        if not q.upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed.")
        if self._engine is None:
            self.connect()
        from sqlalchemy import text
        rows = []
        with self._engine.connect() as conn:
            result = conn.execute(text(self._query))
            self._columns = list(result.keys())
            for row in result:
                rows.append(dict(zip(self._columns, row)))
        return rows

    def get_columns(self) -> list[str]:
        return self._columns

    def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None
