"""Project I/O — save and load .bimap (JSON) files."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from bimap.config import PROJECT_FILE_EXTENSION
from bimap.models.project import Project


class ProjectIOError(Exception):
    pass


def save_project(project: Project, path: Path) -> None:
    """Serialise *project* to *path* (creates/overwrites the file)."""
    if path.suffix.lower() != PROJECT_FILE_EXTENSION:
        path = path.with_suffix(PROJECT_FILE_EXTENSION)
    try:
        data = project.model_dump_json(indent=2)
        path.write_text(data, encoding="utf-8")
        project.file_path = str(path)
    except (OSError, ValueError) as exc:
        raise ProjectIOError(f"Could not save project: {exc}") from exc


def load_project(path: Path) -> Project:
    """Deserialise a .bimap file and return a Project instance."""
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        project = Project.model_validate(data)
        project.file_path = str(path)
        return project
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ProjectIOError(f"Could not load project: {exc}") from exc


def export_backup(project: Project, path: Path) -> None:
    """Export the project as a portable ZIP backup (.bimap.zip)."""
    json_data = project.model_dump_json(indent=2)
    stem = Path(project.file_path).stem if project.file_path else "project"
    entry_name = stem + PROJECT_FILE_EXTENSION
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(entry_name, json_data)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProjectIOError(f"Could not write backup: {exc}") from exc


def import_backup(path: Path) -> Project:
    """Load a project from a ZIP backup or a plain .bimap file."""
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as zf:
                bimap_entries = [n for n in zf.namelist() if n.endswith(PROJECT_FILE_EXTENSION)]
                if not bimap_entries:
                    raise ProjectIOError("No .bimap file found inside the backup archive.")
                raw = zf.read(bimap_entries[0]).decode("utf-8")
        else:
            raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        project = Project.model_validate(data)
        project.file_path = ""   # not bound to a location yet
        return project
    except ProjectIOError:
        raise
    except (OSError, json.JSONDecodeError, ValueError, zipfile.BadZipFile) as exc:
        raise ProjectIOError(f"Could not import backup: {exc}") from exc


def export_elements_csv(project: Project, path: Path) -> None:
    """Export all zones and keypoints with every metadata attribute to a CSV file.

    Each row represents one element.  Base columns (type, id, name, lat, lon,
    layer, group, visible) are always present.  Every *visible* metadata key
    found across all elements is added as additional columns.  Standard derived
    attributes (area_m2, perimeter_m, centroid_lat, centroid_lon, vertex_count)
    are always included as extra columns for zones.
    """
    import csv
    import math as _math

    # Standard computed zone attributes to always include in export
    _DERIVED_ZONE_KEYS = ["area_m2", "perimeter_m", "centroid_lat", "centroid_lon", "vertex_count"]

    # Collect all visible metadata keys across all elements
    all_meta_keys: set[str] = set()
    for z in project.zones:
        hidden = set(getattr(z, "metadata_hidden", []))
        for k in z.metadata:
            if k not in hidden and not k.startswith("__"):
                all_meta_keys.add(k)
    for kp in project.keypoints:
        hidden = set(getattr(kp, "metadata_hidden", []))
        for k in kp.metadata:
            if k not in hidden and not k.startswith("__"):
                all_meta_keys.add(k)

    meta_keys = sorted(all_meta_keys)
    base_fields = ["type", "id", "name", "lat", "lon", "layer", "group", "visible",
                   "zone_type", "radius_m", "width_m", "height_m", "rotation_deg"]
    all_fields = base_fields + _DERIVED_ZONE_KEYS + meta_keys

    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f, fieldnames=all_fields, extrasaction="ignore"
            )
            writer.writeheader()

            for z in project.zones:
                coords = z.coordinates
                if coords:
                    lat = sum(c.lat for c in coords) / len(coords)
                    lon = sum(c.lon for c in coords) / len(coords)
                else:
                    lat = lon = 0.0
                hidden = set(getattr(z, "metadata_hidden", []))
                row: dict = {
                    "type": "zone",
                    "id": str(z.id),
                    "name": z.name,
                    "lat": round(lat, 7),
                    "lon": round(lon, 7),
                    "layer": z.layer,
                    "group": z.group,
                    "visible": z.visible,
                    "zone_type": z.zone_type,
                    "radius_m": z.radius_m if z.zone_type == "circle" else "",
                    "width_m": z.width_m or "",
                    "height_m": z.height_m or "",
                    "rotation_deg": z.rotation_deg if z.rotation_deg else "",
                }
                # Always export standard derived attributes for zones
                for dk in _DERIVED_ZONE_KEYS:
                    row[dk] = z.metadata.get(dk, "")
                for k in meta_keys:
                    row[k] = z.metadata.get(k, "") if k not in hidden else ""
                writer.writerow(row)

            for kp in project.keypoints:
                hidden = set(getattr(kp, "metadata_hidden", []))
                row = {
                    "type": "keypoint",
                    "id": str(kp.id),
                    "name": kp.name,
                    "lat": round(kp.lat, 7),
                    "lon": round(kp.lon, 7),
                    "layer": kp.layer,
                    "group": kp.group,
                    "visible": kp.visible,
                    "zone_type": "",
                    "radius_m": "",
                    "width_m": "",
                    "height_m": "",
                    "rotation_deg": "",
                }
                # Leave derived zone columns empty for keypoints
                for dk in _DERIVED_ZONE_KEYS:
                    row[dk] = ""
                for k in meta_keys:
                    row[k] = kp.metadata.get(k, "") if k not in hidden else ""
                writer.writerow(row)

    except OSError as exc:
        raise ProjectIOError(f"Could not write CSV: {exc}") from exc
