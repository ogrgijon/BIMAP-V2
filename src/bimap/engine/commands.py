"""Undo / Redo command objects using Qt's QUndoCommand."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING
from uuid import UUID

from PyQt6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from bimap.models.project import Project
    from bimap.models.zone import Zone
    from bimap.models.keypoint import Keypoint
    from bimap.models.annotation import Annotation
    from bimap.models.data_source import DataSource
    from bimap.data import DataRefreshManager


# ── Base helpers ──────────────────────────────────────────────────────────────

class _ProjectCommand(QUndoCommand):
    """Base command that holds a reference to the project and a changed signal."""

    def __init__(self, project: "Project", description: str, on_change=None):
        super().__init__(description)
        self._project = project
        self._on_change = on_change  # callable() triggered after redo/undo

    def _notify(self) -> None:
        if self._on_change:
            self._on_change()


# ── Zone commands ─────────────────────────────────────────────────────────────

class AddZoneCommand(_ProjectCommand):
    def __init__(self, project: "Project", zone: "Zone", on_change=None):
        super().__init__(project, f"Add zone '{zone.name}'", on_change)
        self._zone = deepcopy(zone)

    def redo(self) -> None:
        self._project.zones.append(deepcopy(self._zone))
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        self._project.zones = [z for z in self._project.zones if z.id != self._zone.id]
        self._project.mark_modified()
        self._notify()


class RemoveZoneCommand(_ProjectCommand):
    def __init__(self, project: "Project", zone_id, on_change=None):
        super().__init__(project, "Remove zone", on_change)
        self._zone_id = zone_id
        self._zone_backup: "Zone | None" = None

    def redo(self) -> None:
        for z in self._project.zones:
            if z.id == self._zone_id:
                self._zone_backup = deepcopy(z)
                break
        self._project.zones = [z for z in self._project.zones if z.id != self._zone_id]
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        if self._zone_backup:
            self._project.zones.append(deepcopy(self._zone_backup))
        self._project.mark_modified()
        self._notify()


class EditZoneCommand(_ProjectCommand):
    def __init__(self, project: "Project", old_zone: "Zone", new_zone: "Zone", on_change=None):
        super().__init__(project, f"Edit zone '{new_zone.name}'", on_change)
        self._old = deepcopy(old_zone)
        self._new = deepcopy(new_zone)

    def _replace(self, replacement: "Zone") -> None:
        for i, z in enumerate(self._project.zones):
            if z.id == replacement.id:
                self._project.zones[i] = deepcopy(replacement)
                break

    def redo(self) -> None:
        self._replace(self._new)
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        self._replace(self._old)
        self._project.mark_modified()
        self._notify()


# ── Keypoint commands ─────────────────────────────────────────────────────────

class AddKeypointCommand(_ProjectCommand):
    def __init__(self, project: "Project", kp: "Keypoint", on_change=None):
        super().__init__(project, f"Add keypoint '{kp.info_card.title or 'Pin'}'", on_change)
        self._kp = deepcopy(kp)

    def redo(self) -> None:
        self._project.keypoints.append(deepcopy(self._kp))
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        self._project.keypoints = [k for k in self._project.keypoints if k.id != self._kp.id]
        self._project.mark_modified()
        self._notify()


class RemoveKeypointCommand(_ProjectCommand):
    def __init__(self, project: "Project", kp_id, on_change=None):
        super().__init__(project, "Remove keypoint", on_change)
        self._kp_id = kp_id
        self._backup = None

    def redo(self) -> None:
        for k in self._project.keypoints:
            if k.id == self._kp_id:
                self._backup = deepcopy(k)
                break
        self._project.keypoints = [k for k in self._project.keypoints if k.id != self._kp_id]
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        if self._backup:
            self._project.keypoints.append(deepcopy(self._backup))
        self._project.mark_modified()
        self._notify()


class EditKeypointCommand(_ProjectCommand):
    def __init__(self, project: "Project", old_kp: "Keypoint", new_kp: "Keypoint", on_change=None):
        super().__init__(project, "Edit keypoint", on_change)
        self._old = deepcopy(old_kp)
        self._new = deepcopy(new_kp)

    def _replace(self, replacement: "Keypoint") -> None:
        for i, k in enumerate(self._project.keypoints):
            if k.id == replacement.id:
                self._project.keypoints[i] = deepcopy(replacement)
                break

    def redo(self) -> None:
        self._replace(self._new)
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        self._replace(self._old)
        self._project.mark_modified()
        self._notify()


# ── Annotation commands ───────────────────────────────────────────────────────

class AddAnnotationCommand(_ProjectCommand):
    def __init__(self, project: "Project", ann: "Annotation", on_change=None):
        super().__init__(project, "Add annotation", on_change)
        self._ann = deepcopy(ann)

    def redo(self) -> None:
        self._project.annotations.append(deepcopy(self._ann))
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        self._project.annotations = [
            a for a in self._project.annotations if a.id != self._ann.id
        ]
        self._project.mark_modified()
        self._notify()


class RemoveAnnotationCommand(_ProjectCommand):
    def __init__(self, project: "Project", ann_id, on_change=None):
        super().__init__(project, "Remove annotation", on_change)
        self._ann_id = ann_id
        self._backup = None

    def redo(self) -> None:
        for a in self._project.annotations:
            if a.id == self._ann_id:
                self._backup = deepcopy(a)
                break
        self._project.annotations = [
            a for a in self._project.annotations if a.id != self._ann_id
        ]
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        if self._backup:
            self._project.annotations.append(deepcopy(self._backup))
        self._project.mark_modified()
        self._notify()


class EditAnnotationCommand(_ProjectCommand):
    def __init__(self, project: "Project", old_ann: "Annotation", new_ann: "Annotation", on_change=None):
        super().__init__(project, "Edit annotation", on_change)
        self._old = deepcopy(old_ann)
        self._new = deepcopy(new_ann)

    def _replace(self, replacement: "Annotation") -> None:
        for i, a in enumerate(self._project.annotations):
            if a.id == replacement.id:
                self._project.annotations[i] = deepcopy(replacement)
                break

    def redo(self) -> None:
        self._replace(self._new)
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        self._replace(self._old)
        self._project.mark_modified()
        self._notify()


# ── Data source commands ──────────────────────────────────────────────────────

class AddDataSourceCommand(_ProjectCommand):
    """Undo-able add of a DataSource including connector registration."""

    def __init__(self, project: "Project", ds: "DataSource",
                 refresh_manager: "DataRefreshManager",
                 connector, on_change=None) -> None:
        super().__init__(project, f"Add data source '{ds.name}'", on_change)
        self._ds = deepcopy(ds)
        self._refresh_manager = refresh_manager
        self._connector = connector

    def redo(self) -> None:
        self._project.data_sources.append(deepcopy(self._ds))
        self._refresh_manager.register(self._ds, self._connector)
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        sid = str(self._ds.id)
        self._project.data_sources = [
            s for s in self._project.data_sources if str(s.id) != sid
        ]
        self._refresh_manager.unregister(sid)
        self._project.mark_modified()
        self._notify()


class RemoveDataSourceCommand(_ProjectCommand):
    """Undo-able removal of a DataSource."""

    def __init__(self, project: "Project", source_id: str,
                 refresh_manager: "DataRefreshManager", on_change=None) -> None:
        super().__init__(project, "Remove data source", on_change)
        self._source_id = source_id
        self._refresh_manager = refresh_manager
        self._backup: "DataSource | None" = None
        self._connector = None  # saved from manager before unregister

    def redo(self) -> None:
        for ds in self._project.data_sources:
            if str(ds.id) == self._source_id:
                self._backup = deepcopy(ds)
                break
        # Save the connector before unregistering so undo can restore it
        self._connector = self._refresh_manager._connectors.get(self._source_id)
        self._project.data_sources = [
            s for s in self._project.data_sources if str(s.id) != self._source_id
        ]
        self._refresh_manager.unregister(self._source_id)
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        if self._backup:
            restored = deepcopy(self._backup)
            self._project.data_sources.append(restored)
            if self._connector is not None:
                self._refresh_manager.register(restored, self._connector)
        self._project.mark_modified()
        self._notify()


# ── Batch commands ────────────────────────────────────────────────────────────

class RemoveMultipleCommand(_ProjectCommand):
    """Remove a batch of zones and/or keypoints in a single undoable step."""

    def __init__(self, project: "Project",
                 items: list[tuple[str, str]], on_change=None) -> None:
        super().__init__(project, f"Remove {len(items)} element(s)", on_change)
        self._items = items
        self._zone_backups: list = []
        self._kp_backups: list = []

    def redo(self) -> None:
        self._zone_backups.clear()
        self._kp_backups.clear()
        zone_ids = {UUID(eid) for etype, eid in self._items if etype == "zone"}
        kp_ids = {UUID(eid) for etype, eid in self._items if etype == "keypoint"}
        self._zone_backups = [deepcopy(z) for z in self._project.zones
                              if z.id in zone_ids]
        self._kp_backups = [deepcopy(k) for k in self._project.keypoints
                            if k.id in kp_ids]
        self._project.zones = [z for z in self._project.zones
                                if z.id not in zone_ids]
        self._project.keypoints = [k for k in self._project.keypoints
                                   if k.id not in kp_ids]
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        self._project.zones.extend(deepcopy(z) for z in self._zone_backups)
        self._project.keypoints.extend(deepcopy(k) for k in self._kp_backups)
        self._project.mark_modified()
        self._notify()


class MoveElementCommand(_ProjectCommand):
    """Move a zone, keypoint, or annotation to a new lat/lon."""

    def __init__(self, project: "Project", element_type: str, element_id: str,
                 new_lat: float, new_lon: float, on_change=None) -> None:
        super().__init__(project, f"Move {element_type}", on_change)
        self._etype = element_type
        self._eid = UUID(element_id)
        self._new_lat = new_lat
        self._new_lon = new_lon
        self._old_lat: float | None = None
        self._old_lon: float | None = None

    def _find(self):
        if self._etype == "zone":
            return next((z for z in self._project.zones if z.id == self._eid), None)
        if self._etype == "annotation":
            return next((a for a in self._project.annotations if a.id == self._eid), None)
        return next((k for k in self._project.keypoints if k.id == self._eid), None)

    def redo(self) -> None:
        obj = self._find()
        if obj is None:
            return
        if self._etype == "zone":
            if obj.coordinates:
                # Compute centroid shift
                c_lat = sum(p.lat for p in obj.coordinates) / len(obj.coordinates)
                c_lon = sum(p.lon for p in obj.coordinates) / len(obj.coordinates)
                d_lat = self._new_lat - c_lat
                d_lon = self._new_lon - c_lon
                self._old_lat, self._old_lon = c_lat, c_lon
                for coord in obj.coordinates:
                    coord.lat += d_lat
                    coord.lon += d_lon
        elif self._etype == "annotation":
            if obj.ann_type.value == "dimension":
                if obj.dimension_start_lat is None or obj.dimension_end_lat is None:
                    return
                center_lat = (obj.dimension_start_lat + obj.dimension_end_lat) / 2
                center_lon = (obj.dimension_start_lon + obj.dimension_end_lon) / 2
                self._old_lat, self._old_lon = center_lat, center_lon
                d_lat = self._new_lat - center_lat
                d_lon = self._new_lon - center_lon
                obj.dimension_start_lat += d_lat
                obj.dimension_start_lon += d_lon
                obj.dimension_end_lat += d_lat
                obj.dimension_end_lon += d_lon
            elif obj.anchor_lat is not None and obj.anchor_lon is not None:
                self._old_lat, self._old_lon = obj.anchor_lat, obj.anchor_lon
                obj.anchor_lat = self._new_lat
                obj.anchor_lon = self._new_lon
            else:
                self._old_lat, self._old_lon = self._new_lat, self._new_lon
                obj.position.x = self._new_lon
                obj.position.y = self._new_lat
        else:
            self._old_lat, self._old_lon = obj.lat, obj.lon
            obj.lat = self._new_lat
            obj.lon = self._new_lon
        self._project.mark_modified()
        self._notify()

    def undo(self) -> None:
        if self._old_lat is None:
            return
        obj = self._find()
        if obj is None:
            return
        if self._etype == "zone":
            if obj.coordinates:
                d_lat = self._old_lat - self._new_lat
                d_lon = self._old_lon - self._new_lon
                for coord in obj.coordinates:
                    coord.lat += d_lat
                    coord.lon += d_lon
        elif self._etype == "annotation":
            if obj.ann_type.value == "dimension":
                center_lat = (obj.dimension_start_lat + obj.dimension_end_lat) / 2
                center_lon = (obj.dimension_start_lon + obj.dimension_end_lon) / 2
                d_lat = self._old_lat - center_lat
                d_lon = self._old_lon - center_lon
                obj.dimension_start_lat += d_lat
                obj.dimension_start_lon += d_lon
                obj.dimension_end_lat += d_lat
                obj.dimension_end_lon += d_lon
            elif obj.anchor_lat is not None and obj.anchor_lon is not None:
                obj.anchor_lat = self._old_lat
                obj.anchor_lon = self._old_lon
            else:
                obj.position.x = self._old_lon
                obj.position.y = self._old_lat
        else:
            obj.lat = self._old_lat
            obj.lon = self._old_lon
        self._project.mark_modified()
        self._notify()


# ── Metadata command ──────────────────────────────────────────────────────────

class SetMetadataCommand(_ProjectCommand):
    """Add/edit/remove a single metadata key on any Zone, Keypoint, or Annotation."""

    def __init__(self, project: "Project", element_type: str, element_id: str,
                 key: str, new_value: str | None, on_change=None) -> None:
        action = "Remove" if new_value is None else "Set"
        super().__init__(project, f"{action} metadata '{key}'", on_change)
        self._etype = element_type
        self._eid = element_id
        self._key = key
        self._new_value = new_value
        self._old_value: str | None = None

    def _find_element(self):
        match self._etype:
            case "zone":
                return next((z for z in self._project.zones if str(z.id) == self._eid), None)
            case "keypoint":
                return next((k for k in self._project.keypoints if str(k.id) == self._eid), None)
            case "annotation":
                return next((a for a in self._project.annotations if str(a.id) == self._eid), None)
        return None

    def _apply(self, value: str | None) -> None:
        elem = self._find_element()
        if elem is None or not hasattr(elem, "metadata"):
            return
        if value is None:
            elem.metadata.pop(self._key, None)
        else:
            elem.metadata[self._key] = value
            # Keep layer key_library up to date
            layer_name = getattr(elem, "layer", "Default")
            for lyr in self._project.layers:
                if lyr.name == layer_name and self._key not in lyr.key_library:
                    lyr.key_library.append(self._key)
                    break
        self._project.mark_modified()
        self._notify()

    def redo(self) -> None:
        elem = self._find_element()
        if elem and hasattr(elem, "metadata"):
            self._old_value = elem.metadata.get(self._key)
        self._apply(self._new_value)

    def undo(self) -> None:
        self._apply(self._old_value)
