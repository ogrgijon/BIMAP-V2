"""
pytest configuration and shared fixtures.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Force offscreen rendering so Qt widgets can be instantiated in CI / headless
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """Single QApplication instance for the whole test session."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    # Drain thread pool so no QPixmap is created after QApplication is gone
    from PyQt6.QtCore import QThreadPool
    QThreadPool.globalInstance().waitForDone(3000)


@pytest.fixture
def sample_project():
    """A minimal Project with one Zone and one Keypoint."""
    from bimap.models.project import Project
    from bimap.models.zone import Zone, ZoneType, LatLon
    from bimap.models.keypoint import Keypoint

    p = Project(name="Test Project")
    z = Zone(name="Zone A", zone_type=ZoneType.POLYGON,
             coordinates=[LatLon(lat=40.4, lon=-3.7),
                          LatLon(lat=40.5, lon=-3.6),
                          LatLon(lat=40.45, lon=-3.65)])
    p.zones.append(z)

    kp = Keypoint(lat=40.41, lon=-3.70)
    kp.info_card.title = "KP 1"
    kp.keynote_number = 1
    p.keypoints.append(kp)
    return p
