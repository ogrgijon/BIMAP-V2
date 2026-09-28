"""Open icon catalog used by keypoint markers.

The catalog uses Unicode symbols as a dependency-free fallback. A Font
Awesome Free Solid font may be packaged as ``fa-solid-900.ttf``; when it is
available the same entries render with their Font Awesome glyphs.
"""

from __future__ import annotations

from importlib.resources import files

from PyQt6.QtGui import QFontDatabase


# name, label, Font Awesome codepoint, fallback Unicode symbol
ICON_CATALOG: tuple[tuple[str, str, int, str], ...] = (
    ("map-marker", "Map marker", 0xF041, "●"),
    ("tree", "Tree", 0xF1BB, "♣"),
    ("car", "Car", 0xF1B9, "▣"),
    ("bicycle", "Bicycle", 0xF206, "♢"),
    ("bus", "Bus", 0xF207, "▤"),
    ("train", "Train", 0xF238, "▥"),
    ("plane", "Plane", 0xF072, "✈"),
    ("ship", "Ship", 0xF21A, "⚓"),
    ("house", "House", 0xF015, "⌂"),
    ("building", "Building", 0xF1AD, "▥"),
    ("hospital", "Hospital", 0xF0F8, "+"),
    ("school", "School", 0xF549, "▦"),
    ("person", "Person", 0xF007, "●"),
    ("users", "People", 0xF0C0, "●"),
    ("camera", "Camera", 0xF030, "◉"),
    ("flag", "Flag", 0xF024, "⚑"),
    ("star", "Star", 0xF005, "★"),
    ("heart", "Heart", 0xF004, "♥"),
    ("warning", "Warning", 0xF071, "▲"),
    ("info", "Information", 0xF129, "ⓘ"),
)

_font_family: str | None = None
_preferred_family = ""


def icon_value(name: str) -> str:
    """Return the stable serialized value for a catalog entry."""
    return f"fa:{name}"


def icon_entry(value: str) -> tuple[str, str, int, str] | None:
    """Return catalog data for a serialized icon value."""
    if not value.startswith("fa:"):
        return None
    name = value[3:]
    return next((entry for entry in ICON_CATALOG if entry[0] == name), None)


def set_icon_font_family(family: str) -> None:
    """Set the application-wide font used for font-backed keypoint icons."""
    global _preferred_family
    _preferred_family = family.strip()
    _load_bundled_font_family()


def icon_font_family() -> str | None:
    """Return the configured font, or the bundled Font Awesome family."""
    if _preferred_family:
        return _preferred_family
    return _load_bundled_font_family()


def icon_glyph(entry: tuple[str, str, int, str]) -> str:
    """Return the glyph for an entry in the currently selected font."""
    family = icon_font_family()
    bundled = _load_bundled_font_family()
    return chr(entry[2]) if family and family == bundled else entry[3]


def _load_bundled_font_family() -> str | None:
    """Load the optional Font Awesome font once and return its family."""
    global _font_family
    if _font_family is not None:
        return _font_family or None
    try:
        font_path = files("bimap.data").joinpath("fa-solid-900.ttf")
        if not font_path.is_file():
            font_path = files("fontawesomefree").joinpath(
                "static/fontawesomefree/webfonts/fa-solid-900.ttf"
            )
        if font_path.is_file():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            _font_family = families[0] if families else ""
        else:
            _font_family = ""
    except (OSError, TypeError):
        _font_family = ""
    return _font_family or None