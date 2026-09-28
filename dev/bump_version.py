#!/usr/bin/env python3
"""
Bump the version string in pyproject.toml and src/bimap/config.py in sync.

Usage:
    python bump_version.py [major|minor|patch]

Defaults to 'patch' when no argument is given.
"""

import re
import sys
from pathlib import Path


def _bump(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))
    match part:
        case "major":
            return f"{major + 1}.0.0"
        case "minor":
            return f"{major}.{minor + 1}.0"
        case "patch":
            return f"{major}.{minor}.{patch + 1}"
        case _:
            raise ValueError(f"Unknown part '{part}'. Use: major | minor | patch")


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    root = Path(__file__).resolve().parents[1]

    toml_path = root / "pyproject.toml"
    toml_text = toml_path.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', toml_text, re.MULTILINE)
    if not m:
        sys.exit("ERROR: version not found in pyproject.toml")
    old_version = m.group(1)
    new_version = _bump(old_version, part)

    toml_path.write_text(
        toml_text.replace(f'version = "{old_version}"', f'version = "{new_version}"', 1),
        encoding="utf-8",
    )

    config_path = root / "src" / "bimap" / "config.py"
    config_text = config_path.read_text(encoding="utf-8")
    if f'APP_VERSION = "{old_version}"' not in config_text:
        print(f"WARNING: APP_VERSION not found in config.py — pyproject.toml updated only.")
    else:
        config_path.write_text(
            config_text.replace(
                f'APP_VERSION = "{old_version}"', f'APP_VERSION = "{new_version}"', 1
            ),
            encoding="utf-8",
        )

    print(f"Version bumped: {old_version} → {new_version}")


if __name__ == "__main__":
    main()
