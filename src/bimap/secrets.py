"""Credential helpers — store/retrieve secrets via the OS keychain (keyring).

Usage
-----
Save a secret::

    from bimap.secrets import set_secret, get_secret
    set_secret("my-layer-id", "Authorization: Bearer abc123")

Retrieve it::

    auth = get_secret("my-layer-id")  # returns "" if not found

Secrets are stored under the ``bimap`` service name so they are isolated from
other applications.  The *key* is an arbitrary identifier (e.g. a LiveLayer or
DataSource UUID).

Falls back silently to in-memory storage when ``keyring`` is unavailable (e.g.
headless CI environment with no OS keychain).
"""

from __future__ import annotations

_SERVICE = "bimap"
_FALLBACK: dict[str, str] = {}


def set_secret(key: str, value: str) -> None:
    """Persist *value* in the OS keychain under *key*.

    If keyring is unavailable the value is kept only for the process lifetime.
    """
    try:
        import keyring  # type: ignore[import]
        if value:
            keyring.set_password(_SERVICE, key, value)
        else:
            _delete_secret(key)
    except Exception:  # noqa: BLE001
        if value:
            _FALLBACK[key] = value
        else:
            _FALLBACK.pop(key, None)


def get_secret(key: str) -> str:
    """Return the secret stored under *key*, or ``""`` if not found."""
    try:
        import keyring  # type: ignore[import]
        value = keyring.get_password(_SERVICE, key)
        return value or ""
    except Exception:  # noqa: BLE001
        return _FALLBACK.get(key, "")


def _delete_secret(key: str) -> None:
    try:
        import keyring  # type: ignore[import]
        keyring.delete_password(_SERVICE, key)
    except Exception:  # noqa: BLE001
        _FALLBACK.pop(key, None)
