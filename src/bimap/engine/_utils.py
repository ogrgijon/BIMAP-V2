"""Shared engine utility helpers."""

from __future__ import annotations

from typing import Any


def get_nested(data: Any, path: str) -> Any:
    """Traverse a dot-path like 'results.0.lat' through nested dicts/lists.

    Returns ``None`` if the path does not exist or any intermediate
    traversal fails.  List elements can be accessed with numeric keys.
    """
    for key in path.split("."):
        if isinstance(data, dict):
            data = data.get(key)
        elif isinstance(data, list) and key.isdigit():
            data = data[int(key)]
        else:
            return None
        if data is None:
            return None
    return data
