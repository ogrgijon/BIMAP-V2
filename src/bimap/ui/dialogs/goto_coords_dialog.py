"""Dialog for placing a keypoint or polygon zone by entering lat/lon coordinates."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import add_dialog_help_button


class GotoCoordsDialog(QDialog):
    """Accept lat/lon input and return placement data.

    Result is available via :meth:`result_mode` and :meth:`result_coords`
    after :meth:`exec` returns ``Accepted``.

    * Mode ``"keypoint"`` → ``result_coords()`` returns ``[(lat, lon)]``.
    * Mode ``"zone"``     → ``result_coords()`` returns a list of ``(lat, lon)`` tuples
      parsed from the multi-line text box (one ``"lat, lon"`` per line, 3+ vertices).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("Place by Coordinates"))
        self.setMinimumWidth(380)
        self._setup_ui()

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Mode selector
        mode_row = QHBoxLayout()
        self._radio_kp = QRadioButton(t("Keypoint (single point)"))
        self._radio_zone = QRadioButton(t("Zone (polygon vertices)"))
        self._radio_kp.setChecked(True)
        mode_row.addWidget(self._radio_kp)
        mode_row.addWidget(self._radio_zone)
        layout.addLayout(mode_row)

        # ── Keypoint page ─────────────────────────────────────────────────────
        self._kp_widget = QWidget()
        kp_form = QFormLayout(self._kp_widget)
        kp_form.setContentsMargins(0, 4, 0, 0)

        self._lat_spin = QDoubleSpinBox()
        self._lat_spin.setRange(-90.0, 90.0)
        self._lat_spin.setDecimals(6)
        self._lat_spin.setSingleStep(0.001)
        kp_form.addRow(t("Latitude") + ":", self._lat_spin)

        self._lon_spin = QDoubleSpinBox()
        self._lon_spin.setRange(-180.0, 180.0)
        self._lon_spin.setDecimals(6)
        self._lon_spin.setSingleStep(0.001)
        kp_form.addRow(t("Longitude") + ":", self._lon_spin)

        layout.addWidget(self._kp_widget)

        # ── Zone page ────────────────────────────────────────────────────────
        self._zone_widget = QWidget()
        zone_vbox = QVBoxLayout(self._zone_widget)
        zone_vbox.setContentsMargins(0, 4, 0, 0)

        hint = QLabel(t("Enter one vertex per line as:  lat, lon\n(minimum 3 vertices to create a zone)"))
        hint.setStyleSheet("color: #888888; font-size: 10px;")
        hint.setWordWrap(True)
        zone_vbox.addWidget(hint)

        self._vertices_edit = QPlainTextEdit()
        self._vertices_edit.setPlaceholderText("40.712776, -74.005974\n48.856613,  2.352222\n51.507351, -0.127758")
        self._vertices_edit.setMinimumHeight(120)
        zone_vbox.addWidget(self._vertices_edit)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #E74C3C; font-size: 10px;")
        self._error_label.setWordWrap(True)
        zone_vbox.addWidget(self._error_label)

        layout.addWidget(self._zone_widget)
        self._zone_widget.setVisible(False)

        # Toggle visibility when mode changes
        self._radio_kp.toggled.connect(self._on_mode_toggled)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        add_dialog_help_button(buttons, self, "Place by Coordinates window help")
        layout.addWidget(buttons)

    def _on_mode_toggled(self, kp_active: bool) -> None:
        self._kp_widget.setVisible(kp_active)
        self._zone_widget.setVisible(not kp_active)
        self._error_label.setText("")

    # ── Validation ────────────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        if self._radio_zone.isChecked():
            coords, err = self._parse_vertices()
            if err:
                self._error_label.setText(err)
                return
            self._coords = coords
        else:
            self._coords = [(self._lat_spin.value(), self._lon_spin.value())]
        self.accept()

    def _parse_vertices(self) -> tuple[list[tuple[float, float]], str]:
        lines = [ln.strip() for ln in self._vertices_edit.toPlainText().splitlines() if ln.strip()]
        if len(lines) < 3:
            return [], t("At least 3 vertices are required to create a zone.")
        coords: list[tuple[float, float]] = []
        for i, line in enumerate(lines, 1):
            parts = line.replace(";", ",").split(",")
            if len(parts) != 2:
                return [], t(f"Line {i}: expected 'lat, lon' but got: {line!r}")
            try:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
            except ValueError:
                return [], t(f"Line {i}: could not parse numbers from: {line!r}")
            if not (-90 <= lat <= 90):
                return [], t(f"Line {i}: latitude {lat} is out of range [-90, 90].")
            if not (-180 <= lon <= 180):
                return [], t(f"Line {i}: longitude {lon} is out of range [-180, 180].")
            coords.append((lat, lon))
        return coords, ""

    # ── Result accessors ──────────────────────────────────────────────────────

    def result_mode(self) -> str:
        """Return ``'keypoint'`` or ``'zone'``."""
        return "keypoint" if self._radio_kp.isChecked() else "zone"

    def result_coords(self) -> list[tuple[float, float]]:
        """Return the parsed coordinate list set by :meth:`_on_accept`."""
        return getattr(self, "_coords", [])
