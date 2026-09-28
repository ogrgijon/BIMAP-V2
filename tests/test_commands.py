"""
Tests for engine/commands.py — undo/redo operations.
"""

from __future__ import annotations

import copy
from uuid import UUID

import pytest

from bimap.models.project import Project
from bimap.models.zone import Zone, ZoneType, LatLon
from bimap.models.keypoint import Keypoint
from bimap.models.annotation import Annotation, AnnotationType
from bimap.engine.commands import (
    AddZoneCommand,
    RemoveZoneCommand,
    EditZoneCommand,
    AddKeypointCommand,
    RemoveKeypointCommand,
    EditKeypointCommand,
    AddAnnotationCommand,
    RemoveAnnotationCommand,
    EditAnnotationCommand,
    MoveElementCommand,
)


@pytest.fixture
def project():
    return Project()


class TestZoneCommands:
    def test_add_redo_undo(self, project):
        z = Zone(name="A", zone_type=ZoneType.POLYGON)
        cmd = AddZoneCommand(project, z)
        cmd.redo()
        assert len(project.zones) == 1
        cmd.undo()
        assert len(project.zones) == 0

    def test_remove_redo_undo(self, project):
        z = Zone(name="B", zone_type=ZoneType.RECTANGLE)
        project.zones.append(z)
        cmd = RemoveZoneCommand(project, z.id)
        cmd.redo()
        assert len(project.zones) == 0
        cmd.undo()
        assert len(project.zones) == 1
        assert project.zones[0].name == "B"

    def test_edit_redo_undo(self, project):
        z = Zone(name="Original")
        project.zones.append(z)
        old = copy.deepcopy(z)
        z_new = copy.deepcopy(z)
        z_new.name = "Edited"
        cmd = EditZoneCommand(project, old, z_new)
        cmd.redo()
        assert project.zones[0].name == "Edited"
        cmd.undo()
        assert project.zones[0].name == "Original"

    def test_on_change_callback_called(self, project):
        calls = []
        z = Zone(name="C")
        cmd = AddZoneCommand(project, z, on_change=lambda: calls.append(1))
        cmd.redo()
        assert len(calls) == 1
        cmd.undo()
        assert len(calls) == 2


class TestKeypointCommands:
    def test_add_redo_undo(self, project):
        kp = Keypoint(lat=40.0, lon=-3.5)
        kp.info_card.title = "KP"
        cmd = AddKeypointCommand(project, kp)
        cmd.redo()
        assert len(project.keypoints) == 1
        cmd.undo()
        assert len(project.keypoints) == 0

    def test_remove_redo_undo(self, project):
        kp = Keypoint(lat=41.0, lon=-4.0)
        kp.info_card.title = "KP2"
        project.keypoints.append(kp)
        cmd = RemoveKeypointCommand(project, kp.id)
        cmd.redo()
        assert len(project.keypoints) == 0
        cmd.undo()
        assert len(project.keypoints) == 1


class TestAnnotationCommands:
    def test_add_redo_undo(self, project):
        ann = Annotation(annotation_type=AnnotationType.TEXT_BOX, text="Hello")
        cmd = AddAnnotationCommand(project, ann)
        cmd.redo()
        assert len(project.annotations) == 1
        cmd.undo()
        assert len(project.annotations) == 0

    def test_move_dimension_redo_undo_preserves_length(self, project):
        ann = Annotation(
            ann_type=AnnotationType.DIMENSION,
            dimension_start_lat=40.0,
            dimension_start_lon=-3.5,
            dimension_end_lat=40.0,
            dimension_end_lon=-3.4,
        )
        project.annotations.append(ann)
        cmd = MoveElementCommand(project, "annotation", str(ann.id), 41.0, -2.0)

        cmd.redo()
        moved = project.annotations[0]
        assert moved.dimension_start_lat == 41.0
        assert moved.dimension_start_lon == -2.05
        assert moved.dimension_end_lat == 41.0
        assert moved.dimension_end_lon == pytest.approx(-1.95)

        cmd.undo()
        restored = project.annotations[0]
        assert restored.dimension_start_lat == 40.0
        assert restored.dimension_start_lon == -3.5
        assert restored.dimension_end_lon == pytest.approx(-3.4)
