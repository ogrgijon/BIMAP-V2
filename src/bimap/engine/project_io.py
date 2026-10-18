"""Project I/O — save and load .bimap (JSON) files."""

from __future__ import annotations

import json
import zipfile
import sqlite3
import struct
import re
from uuid import UUID, uuid4
from pathlib import Path

from bimap.config import PROJECT_FILE_EXTENSION
from bimap.models.project import Project
from bimap.models.zone import LatLon, Zone, ZoneType
from bimap.models.keypoint import Keypoint


class ProjectIOError(Exception):
    pass


CONFLICT_POLICIES = ("update_attributes", "overwrite", "duplicate")


def _element_lists(project: Project):
    return (project.zones, project.keypoints)


def _find_element(project: Project, element_id: UUID):
    for elements in _element_lists(project):
        for element in elements:
            if element.id == element_id:
                return elements, element
    return None, None


def _duplicate_name(name: str, existing: list[str]) -> str:
    pattern = re.compile(rf"^{re.escape(name)} duplicado-(\d+)$")
    numbers = [int(m.group(1)) for value in existing if (m := pattern.match(value))]
    return f"{name} duplicado-{max(numbers, default=0) + 1}"


def resolve_element_conflict(project: Project, incoming, policy: str = "update_attributes"):
    """Insert *incoming* using a deterministic UUID conflict policy.

    ``update_attributes`` changes the existing element's editable attributes,
    ``overwrite`` replaces the complete element, and ``duplicate`` assigns a
    new UUID and a ``duplicado-n`` name suffix.
    """
    if policy not in CONFLICT_POLICIES:
        raise ValueError(f"Unknown conflict policy: {policy}")
    elements, existing = _find_element(project, incoming.id)
    if existing is None:
        elements = project.zones if isinstance(incoming, Zone) else project.keypoints
        elements.append(incoming)
        return incoming
    if policy == "duplicate":
        names = [str(e.name) for lists in _element_lists(project) for e in lists]
        incoming.id = uuid4()
        incoming.name = _duplicate_name(str(incoming.name), names)
        elements.append(incoming)
        return incoming
    if policy == "overwrite":
        elements[elements.index(existing)] = incoming
        return incoming
    # Attribute-only update deliberately retains the existing UUID and geometry.
    old_id = existing.id
    geometry_fields = {"id", "coordinates", "lat", "lon"}
    for key, value in incoming.model_dump().items():
        if key not in geometry_fields:
            setattr(existing, key, value)
    existing.id = old_id
    return existing


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
    all_fields = base_fields + ["geometry", "properties"] + _DERIVED_ZONE_KEYS + meta_keys

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
                    "geometry": json.dumps([c.model_dump() for c in z.coordinates]),
                    "properties": json.dumps(z.model_dump(mode="json")),
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
                    "geometry": json.dumps({"lat": kp.lat, "lon": kp.lon}),
                    "properties": json.dumps(kp.model_dump(mode="json")),
                }
                # Leave derived zone columns empty for keypoints
                for dk in _DERIVED_ZONE_KEYS:
                    row[dk] = ""
                for k in meta_keys:
                    row[k] = kp.metadata.get(k, "") if k not in hidden else ""
                writer.writerow(row)

    except OSError as exc:
        raise ProjectIOError(f"Could not write CSV: {exc}") from exc


def _element_from_row(row: dict):
    """Build an element from the interoperable CSV/Excel row representation."""
    try:
        element_id = UUID(str(row["id"]))
    except (ValueError, KeyError, TypeError):
        element_id = uuid4()
    raw = row.get("properties")
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            data["id"] = element_id
            return Zone.model_validate(data) if row.get("type") == "zone" else Keypoint.model_validate(data)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    name = str(row.get("name") or "Zone")
    try:
        geometry = json.loads(row.get("geometry", "")) if row.get("geometry") else None
    except (TypeError, json.JSONDecodeError):
        geometry = None
    metadata = {str(k): v for k, v in row.items()
                if k not in {"type", "id", "name", "lat", "lon", "layer", "group", "visible",
                             "geometry", "properties"} and v not in ("", None)}
    if row.get("type") == "keypoint":
        return Keypoint(id=element_id, name=name, lat=float(row.get("lat") or 0),
                        lon=float(row.get("lon") or 0), layer=str(row.get("layer") or "Default"),
                        group=str(row.get("group") or "Default"), visible=str(row.get("visible", "True")).lower() != "false",
                        metadata=metadata)
    coords = [LatLon.model_validate(c) for c in (geometry if isinstance(geometry, list) else [])]
    if not coords:
        coords = [LatLon(lat=float(row.get("lat") or 0), lon=float(row.get("lon") or 0))]
    try:
        zone_type = ZoneType(str(row.get("zone_type") or "polygon"))
    except ValueError:
        zone_type = ZoneType.POLYGON
    return Zone(id=element_id, name=name, zone_type=zone_type, coordinates=coords,
                layer=str(row.get("layer") or "Default"), group=str(row.get("group") or "Default"),
                visible=str(row.get("visible", "True")).lower() != "false", metadata=metadata,
                radius_m=float(row.get("radius_m") or 500), width_m=float(row.get("width_m") or 0),
                height_m=float(row.get("height_m") or 0), rotation_deg=float(row.get("rotation_deg") or 0))


def _prepare_import_element(project: Project, incoming, target_layer: str | None):
    if not target_layer:
        return incoming
    # A new layer is an explicit copy operation: never update an existing UUID.
    if _find_element(project, incoming.id)[1] is not None:
        incoming.id = uuid4()
    incoming.layer = target_layer
    incoming.metadata[f"{target_layer}-{incoming.id}"] = str(incoming.id)
    return incoming


def import_elements_csv(project: Project, path: Path, conflict_policy: str = "update_attributes",
                        target_layer: str | None = None) -> int:
    import csv
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            count = 0
            for row in csv.DictReader(f):
                if row.get("type") in {"zone", "keypoint"}:
                    resolve_element_conflict(project, _prepare_import_element(project, _element_from_row(row), target_layer),
                                             conflict_policy)
                    count += 1
            project.mark_modified()
            return count
    except (OSError, csv.Error, ValueError) as exc:
        raise ProjectIOError(f"Could not read CSV: {exc}") from exc


def export_elements_excel(project: Project, path: Path) -> None:
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise ProjectIOError("Excel support requires openpyxl.") from exc
    rows = []
    for elements, kind in ((project.zones, "zone"), (project.keypoints, "keypoint")):
        for element in elements:
            row = {"type": kind, "id": str(element.id), "name": element.name,
                   "geometry": json.dumps(element.model_dump(mode="json")), "properties": json.dumps(element.model_dump(mode="json"))}
            rows.append(row)
    wb = Workbook()
    ws = wb.active
    ws.append(["type", "id", "name", "geometry", "properties"])
    for row in rows:
        ws.append([row[k] for k in ("type", "id", "name", "geometry", "properties")])
    wb.save(path)


def import_elements_excel(project: Project, path: Path, conflict_policy: str = "update_attributes",
                          target_layer: str | None = None) -> int:
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        headers = [str(c.value) for c in next(ws.iter_rows())]
        count = 0
        for values in ws.iter_rows(values_only=True):
            row = dict(zip(headers, values))
            if row.get("type") in {"zone", "keypoint"}:
                resolve_element_conflict(project, _prepare_import_element(project, _element_from_row(row), target_layer),
                                         conflict_policy)
                count += 1
        project.mark_modified()
        return count
    except ImportError as exc:
        raise ProjectIOError("Excel support requires openpyxl.") from exc
    except (OSError, ValueError) as exc:
        raise ProjectIOError(f"Could not read Excel: {exc}") from exc


def import_elements_geopackage(
        project: Project, path: Path, conflict_policy: str = "update_attributes",
        target_layer: str | None = None
) -> int:
        """Import the MerekaiBIMAP ``elements`` GeoPackage table into a project."""
        from bimap.data.geopackage_source import GeoPackageSource

        source = GeoPackageSource(str(path), table_name="elements")
        source.connect()
        count = 0
        for row in source.fetch():
            try:
                element_id = UUID(str(row.get("id")))
                props = json.loads(row.get("properties") or "{}")
                coords = json.loads(row.get("_coordinates") or "[]")
                geom_type = row.get("_geom_type")
                if row.get("type") == "keypoint" or geom_type == "Point":
                    incoming = Keypoint(
                        id=element_id, name=str(row.get("name") or "Keypoint"),
                        lat=float(coords[1]), lon=float(coords[0]),
                    )
                    incoming.layer = str(row.get("layer") or "Default")
                    incoming.metadata = {str(k): str(v) for k, v in props.items()}
                else:
                    incoming = Zone(
                        id=element_id, name=str(row.get("name") or "Line"),
                        zone_type=ZoneType.LINE if geom_type == "LineString" else ZoneType.POLYGON,
                        coordinates=[LatLon(lat=float(point[1]), lon=float(point[0])) for point in coords],
                    )
                    incoming.layer = str(row.get("layer") or "Default")
                    incoming.metadata = {str(k): str(v) for k, v in props.items()}
                resolve_element_conflict(project, _prepare_import_element(project, incoming, target_layer),
                                         conflict_policy)
                count += 1
            except (KeyError, TypeError, ValueError, IndexError, json.JSONDecodeError) as exc:
                raise ProjectIOError(f"Invalid GeoPackage element: {exc}") from exc
        return count
def export_elements_geopackage(project: Project, path: Path) -> None:
    """Export zones and keypoints to a standards-compliant GeoPackage."""
    try:
        db = sqlite3.connect(path)
        try:
            db.executescript(
                "CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT, "
                "identifier TEXT, description TEXT, last_change TEXT, min_x REAL, min_y REAL, "
                "max_x REAL, max_y REAL, srs_id INTEGER);"
                "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
                "geometry_type_name TEXT, srs_id INTEGER, z TINYINT, m TINYINT, "
                "PRIMARY KEY(table_name, column_name));"
                "CREATE TABLE elements (fid INTEGER PRIMARY KEY, type TEXT, id TEXT, name TEXT, "
                "layer TEXT, properties TEXT, geom BLOB NOT NULL);"
            )
            db.execute("INSERT INTO gpkg_contents VALUES ('elements','features','elements','',datetime('now'),NULL,NULL,NULL,NULL,4326)")
            db.execute("INSERT INTO gpkg_geometry_columns VALUES ('elements','geom','GEOMETRY',4326,0,0)")
            fid = 0
            for kind, element in [( "zone", z) for z in project.zones] + [( "keypoint", k) for k in project.keypoints]:
                if kind == "keypoint":
                    coords = [(element.lon, element.lat)]
                    geom = _wkb_point(*coords[0])
                    name = element.name
                    props = element.metadata
                else:
                    coords = [(c.lon, c.lat) for c in element.coordinates]
                    geom = _wkb_linestring(coords) if element.zone_type.value == "line" else _wkb_polygon(coords)
                    name = element.name
                    props = element.metadata
                fid += 1
                db.execute("INSERT INTO elements VALUES (?,?,?,?,?,?,?)", (fid, kind, str(element.id), name, element.layer, json.dumps(props), geom))
            db.commit()
        finally:
            db.close()
    except (OSError, sqlite3.Error, ValueError, IndexError) as exc:
        raise ProjectIOError(f"Could not write GeoPackage: {exc}") from exc


def _wkb_point(x: float, y: float) -> bytes:
    return struct.pack("<BIdd", 1, 1, x, y)


def _wkb_polygon(coords: list[tuple[float, float]]) -> bytes:
    ring = coords + ([coords[0]] if coords[-1] != coords[0] else [])
    return struct.pack("<BII", 1, 3, 1) + struct.pack("<I", len(ring)) + b"".join(struct.pack("<dd", *p) for p in ring)


def _wkb_linestring(coords: list[tuple[float, float]]) -> bytes:
    return struct.pack("<BII", 1, 2, len(coords)) + b"".join(
        struct.pack("<dd", *point) for point in coords
    )
