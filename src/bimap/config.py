"""App-wide configuration and constants."""

from __future__ import annotations

import os
from dataclasses import dataclass as _dataclass
from pathlib import Path

# ── Application ──────────────────────────────────────────────────────────────
APP_NAME = "BIMAP"
APP_VERSION = "0.1.0"
APP_ORGANISATION = "BIMAP"

# ── Paths ─────────────────────────────────────────────────────────────────────
HOME_DIR: Path = Path.home()
APP_DATA_DIR: Path = HOME_DIR / ".bimap"
TILE_CACHE_DIR: Path = APP_DATA_DIR / "tile_cache"
PROJECTS_DIR: Path = APP_DATA_DIR / "projects"
THEME_QSS_PATH: Path = Path(__file__).parent / "ui" / "dark_theme.qss"

for _d in (APP_DATA_DIR, TILE_CACHE_DIR, PROJECTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Map ───────────────────────────────────────────────────────────────────────
TILE_SIZE: int = 256
MIN_ZOOM: int = 1
MAX_ZOOM: int = 21
DEFAULT_ZOOM: int = 12
DEFAULT_CENTER_LAT: float = 43.5453   # Gijón, Asturias
DEFAULT_CENTER_LON: float = -5.6615

# ── Tile Providers ────────────────────────────────────────────────────────────
TILE_PROVIDERS: dict[str, dict] = {
    "osm_standard": {
        "label": "OpenStreetMap Standard",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "max_zoom": 19,
        "attribution": "© OpenStreetMap contributors",
    },
    "cartodb_light": {
        "label": "CartoDB Positron (Light)",
        "url": "https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
        "max_zoom": 19,
        "attribution": "© OpenStreetMap contributors © CartoDB",
    },
    "cartodb_dark": {
        "label": "CartoDB Dark Matter",
        "url": "https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
        "max_zoom": 19,
        "attribution": "© OpenStreetMap contributors © CartoDB",
    },
    "topo": {
        "label": "OpenTopoMap",
        "url": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
        "max_zoom": 17,
        "attribution": "© OpenTopoMap contributors",
    },
}
DEFAULT_TILE_PROVIDER: str = "osm_standard"

# ── HTTP Headers (OSM usage policy requires a meaningful User-Agent) ─────────
HTTP_HEADERS: dict[str, str] = {
    "User-Agent": f"{APP_NAME}/{APP_VERSION} (https://github.com/ogrgijon/BIMAP)",
    "Accept": "image/png,image/*,*/*",
}

# ── Tile Cache ────────────────────────────────────────────────────────────────
TILE_CACHE_SIZE_BYTES: int = 512 * 1024 * 1024   # 512 MB
TILE_CACHE_EXPIRE_DAYS: int = 7

# ── Geocoding ─────────────────────────────────────────────────────────────────
NOMINATIM_URL: str = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT: str = f"{APP_NAME}/{APP_VERSION}"

# ── Drawing ───────────────────────────────────────────────────────────────────
DEFAULT_ZONE_COLOR: str = "#3388FF"
DEFAULT_ZONE_ALPHA: int = 80          # 0-255
DEFAULT_ZONE_BORDER_WIDTH: int = 2
DEFAULT_KEYPOINT_COLOR: str = "#E74C3C"
DEFAULT_KEYPOINT_SIZE: int = 14

# ── PDF Export ────────────────────────────────────────────────────────────────
PDF_DEFAULT_DPI: int = 300
PDF_PAGE_SIZES: dict[str, tuple[float, float]] = {
    # (width_pts, height_pts) in portrait at 72 DPI
    "A4":     (595.27, 841.89),
    "A3":     (841.89, 1190.55),
    "Letter": (612.0,  792.0),
    "Legal":  (612.0,  1008.0),
}
PDF_PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    # (width_mm, height_mm) in portrait — authoritative for QPdfWriter
    "A4":     (210.0,  297.0),
    "A3":     (297.0,  420.0),
    "Letter": (215.9,  279.4),
    "Legal":  (215.9,  355.6),
}

# ── Project file ──────────────────────────────────────────────────────────────
PROJECT_FILE_EXTENSION: str = ".bimap"

# ── Auto-save ────────────────────────────────────────────────────────────────
AUTOSAVE_INTERVAL_MS: int = 60_000   # 1 minute

# ── Undo ─────────────────────────────────────────────────────────────────────
UNDO_STACK_LIMIT: int = 100

# ── User Preferences ─────────────────────────────────────────────────────────


@_dataclass
class Settings:
    """Mutable snapshot of all user preferences."""
    language: str = "en"
    autosave_interval_ms: int = AUTOSAVE_INTERVAL_MS
    undo_stack_limit: int = UNDO_STACK_LIMIT
    startup_mode: str = "none"           # "none" | "last"
    default_zoom: int = DEFAULT_ZOOM
    default_lat: float = DEFAULT_CENTER_LAT
    default_lon: float = DEFAULT_CENTER_LON
    tile_provider: str = DEFAULT_TILE_PROVIDER
    show_scale_bar: bool = True
    show_north_arrow: bool = True
    grid_scale: float = 1.0          # 0.5=fine, 1.0=normal, 2.0=coarse, 4.0=very coarse
    tile_cache_max_mb: int = 512
    tile_cache_expiry_days: int = TILE_CACHE_EXPIRE_DAYS
    projects_dir: str = ""
    keypoint_icon_font_family: str = ""
    # Live feed settings
    live_network_timeout_s: int = 10
    live_max_markers: int = 5000
    live_trail_default: int = 0
    live_follow_fastest: bool = False
    live_show_error_badge: bool = True


def load_user_settings() -> Settings:
    """Read persisted preferences from QSettings and return a Settings instance."""
    from PyQt6.QtCore import QSettings as _QS
    s = _QS(APP_NAME, APP_NAME)
    return Settings(
        language=str(s.value("language", "en")),
        autosave_interval_ms=int(s.value("autosave_interval_ms", AUTOSAVE_INTERVAL_MS)),
        undo_stack_limit=int(s.value("undo_stack_limit", UNDO_STACK_LIMIT)),
        startup_mode=str(s.value("startup_mode", "none")),
        default_zoom=int(s.value("default_zoom", DEFAULT_ZOOM)),
        default_lat=float(s.value("default_lat", DEFAULT_CENTER_LAT)),
        default_lon=float(s.value("default_lon", DEFAULT_CENTER_LON)),
        tile_provider=str(s.value("tile_provider", DEFAULT_TILE_PROVIDER)),
        show_scale_bar=s.value("show_scale_bar", True, type=bool),
        show_north_arrow=s.value("show_north_arrow", True, type=bool),
        grid_scale=float(s.value("grid_scale", 1.0)),
        tile_cache_max_mb=int(s.value("tile_cache_max_mb", TILE_CACHE_SIZE_BYTES // (1024 * 1024))),
        tile_cache_expiry_days=int(s.value("tile_cache_expiry_days", TILE_CACHE_EXPIRE_DAYS)),
        projects_dir=str(s.value("projects_dir", "")),
        keypoint_icon_font_family=str(s.value("keypoint_icon_font_family", "")),
        live_network_timeout_s=int(s.value("live_network_timeout_s", 10)),
        live_max_markers=int(s.value("live_max_markers", 5000)),
        live_trail_default=int(s.value("live_trail_default", 0)),
        live_follow_fastest=s.value("live_follow_fastest", False, type=bool),
        live_show_error_badge=s.value("live_show_error_badge", True, type=bool),
    )


def save_user_settings(settings: Settings) -> None:
    """Persist a Settings instance to QSettings."""
    from PyQt6.QtCore import QSettings as _QS
    s = _QS(APP_NAME, APP_NAME)
    s.setValue("language", settings.language)
    s.setValue("autosave_interval_ms", settings.autosave_interval_ms)
    s.setValue("undo_stack_limit", settings.undo_stack_limit)
    s.setValue("startup_mode", settings.startup_mode)
    s.setValue("default_zoom", settings.default_zoom)
    s.setValue("default_lat", settings.default_lat)
    s.setValue("default_lon", settings.default_lon)
    s.setValue("tile_provider", settings.tile_provider)
    s.setValue("show_scale_bar", settings.show_scale_bar)
    s.setValue("show_north_arrow", settings.show_north_arrow)
    s.setValue("grid_scale", settings.grid_scale)
    s.setValue("tile_cache_max_mb", settings.tile_cache_max_mb)
    s.setValue("tile_cache_expiry_days", settings.tile_cache_expiry_days)
    s.setValue("projects_dir", settings.projects_dir)
    s.setValue("keypoint_icon_font_family", settings.keypoint_icon_font_family)
    s.setValue("live_network_timeout_s", settings.live_network_timeout_s)
    s.setValue("live_max_markers", settings.live_max_markers)
    s.setValue("live_trail_default", settings.live_trail_default)
    s.setValue("live_follow_fastest", settings.live_follow_fastest)
    s.setValue("live_show_error_badge", settings.live_show_error_badge)
