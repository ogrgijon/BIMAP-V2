"""Layers panel — shows map elements organised by layer."""

from __future__ import annotations

import csv
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bimap.i18n import t
from bimap.ui._utils import create_help_button, show_help_dialog

# UserRole data stored on tree items
_ROLE = Qt.ItemDataRole.UserRole


class _LayerTree(QTreeWidget):
    """QTreeWidget that intercepts drops to handle layer reassignment."""

    item_layer_changed = pyqtSignal(str, str, str)  # etype, eid, new_layer_name

    def dropEvent(self, event) -> None:  # type: ignore[override]
        dragged = self.currentItem()
        if dragged is None:
            event.ignore()
            return
        d = dragged.data(0, _ROLE)
        if not d or d[0] == "_layer":
            event.ignore()
            return
        etype, eid = d

        # Find the layer item under the drop position
        drop_pos = event.position().toPoint()
        target = self.itemAt(drop_pos)
        if target is None:
            event.ignore()
            return
        while target.parent() is not None:
            target = target.parent()
        layer_data = target.data(0, _ROLE)
        if not layer_data or layer_data[0] != "_layer":
            event.ignore()
            return

        self.item_layer_changed.emit(etype, eid, layer_data[1])
        event.accept()  # caller calls refresh() — don't let Qt re-order raw items


class LayersPanel(QWidget):
    """
    Tree panel listing map elements grouped by layer.

    Signals
    -------
    element_selected(element_type, id_str)
    element_visibility_changed(element_type, id_str, visible)
    element_delete_requested(element_type, id_str)
    layer_visibility_changed(layer_name, visible)
    layer_add_requested()
    layer_remove_requested(layer_name)
    """

    element_selected = pyqtSignal(str, str)
    element_visibility_changed = pyqtSignal(str, str, bool)
    element_delete_requested = pyqtSignal(str, str)
    layer_visibility_changed = pyqtSignal(str, bool)
    layer_add_requested = pyqtSignal()
    layer_remove_requested = pyqtSignal(str)
    element_action_requested = pyqtSignal(str, str, str)  # action, etype, eid
    element_layer_changed = pyqtSignal(str, str, str)     # etype, eid, new_layer
    data_layer_visibility_changed = pyqtSignal(str, bool) # data_layer_id, visible
    data_layer_opacity_changed = pyqtSignal(str, float)   # data_layer_id, opacity
    data_layer_edit_requested = pyqtSignal(str)           # source_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Any = None
        self._setup_ui()

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        header = QLabel(t("Layers"))
        header.setStyleSheet("font-weight: bold; padding: 2px;")
        header_row.addWidget(header, 1)
        header_row.addWidget(create_help_button(self, self._show_help))
        layout.addLayout(header_row)

        # ── Splitter: regular layers (top) + data layers (bottom) ─────────── #
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # ── Top half: map element layers ───────────────────────────────────── #
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(2)

        self._tree = _LayerTree()
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.setToolTip(t("Check layers and elements to show or hide them; right-click for actions"))
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.item_layer_changed.connect(self.element_layer_changed)
        top_layout.addWidget(self._tree)

        row1 = QHBoxLayout()
        btn_add = QPushButton(t("+ Layer"))
        btn_add.setToolTip(t("Add a new layer"))
        btn_add.clicked.connect(self.layer_add_requested)
        row1.addWidget(btn_add)
        top_layout.addLayout(row1)

        btn_csv = QPushButton(t("Export Layer CSV…"))
        btn_csv.setToolTip(t("Export elements of the selected layer to CSV"))
        btn_csv.clicked.connect(self._on_export_csv)
        top_layout.addWidget(btn_csv)

        splitter.addWidget(top_widget)

        # ── Bottom half: data layers ───────────────────────────────────────── #
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(2)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        bottom_layout.addWidget(sep)

        dl_header_row = QHBoxLayout()
        dl_header = QLabel(t("📊 Data Layers"))
        dl_header.setStyleSheet("font-weight: bold; padding: 2px;")
        dl_header_row.addWidget(dl_header, 1)
        dl_header_row.addWidget(create_help_button(self, self._show_data_layers_help))
        bottom_layout.addLayout(dl_header_row)

        self._data_tree = QTreeWidget()
        self._data_tree.setColumnCount(2)
        self._data_tree.setHeaderLabels([t("Name"), t("Opacity")])
        self._data_tree.setColumnWidth(0, 120)
        self._data_tree.setHeaderHidden(False)
        self._data_tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._data_tree.setDragEnabled(False)
        self._data_tree.setAcceptDrops(False)
        self._data_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._data_tree.setToolTip(t("Check data layers to show or hide them; adjust opacity with the slider"))
        self._data_tree.itemChanged.connect(self._on_data_item_changed)
        self._data_tree.customContextMenuRequested.connect(self._on_data_layer_context_menu)
        bottom_layout.addWidget(self._data_tree)

        splitter.addWidget(bottom_widget)
        # Give bottom a reasonable initial fraction of space
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def _show_help(self) -> None:
        show_help_dialog(self, t("Panel Help"), t("Layers panel help"))

    def _show_data_layers_help(self) -> None:
        show_help_dialog(self, t("Panel Help"), t("Data Layers help"))

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self, project: Any) -> None:
        """Rebuild the entire tree from *project*."""
        self._project = project

        self._tree.blockSignals(True)
        self._tree.clear()

        # Build layer→elements mapping preserving layer order from project
        layer_elements: dict[str, list[tuple[str, Any]]] = {}
        for layer in project.layers:
            layer_elements[layer.name] = []

        # Distribute elements; unknown layers get appended on the fly
        for zone in project.zones:
            ln = getattr(zone, "layer", "Default")
            layer_elements.setdefault(ln, []).append(("zone", zone))

        for kp in project.keypoints:
            ln = getattr(kp, "layer", "Default")
            layer_elements.setdefault(ln, []).append(("keypoint", kp))

        for ann in project.annotations:
            ln = getattr(ann, "layer", "Default")
            layer_elements.setdefault(ln, []).append(("annotation", ann))

        layer_visible = {lyr.name: lyr.visible for lyr in project.layers}

        bold = QFont()
        bold.setBold(True)

        for layer_name, elements in layer_elements.items():
            layer_item = QTreeWidgetItem([layer_name])
            layer_item.setData(0, _ROLE, ("_layer", layer_name))
            visible = layer_visible.get(layer_name, True)
            layer_item.setCheckState(0, Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked)
            layer_item.setFlags(
                layer_item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            layer_item.setFont(0, bold)
            self._tree.addTopLevelItem(layer_item)
            layer_item.setExpanded(True)

            for etype, elem in elements:
                if etype == "zone":
                    label = elem.name
                elif etype == "keypoint":
                    label = elem.info_card.title or "Pin"
                else:
                    label = (elem.content[:30] if elem.content else "") or str(elem.ann_type)

                child = QTreeWidgetItem([f"  {label}"])
                child.setData(0, _ROLE, (etype, str(elem.id)))
                child.setCheckState(
                    0,
                    Qt.CheckState.Checked if getattr(elem, "visible", True) else Qt.CheckState.Unchecked,
                )
                child.setFlags(
                    child.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                layer_item.addChild(child)

        self._tree.blockSignals(False)

        # ── Data Layers section (separate tree) ──────────────────────────────
        self._data_tree.blockSignals(True)
        self._data_tree.clear()
        dl_list = getattr(project, "data_layers", [])
        for dl in dl_list:
            item = QTreeWidgetItem([f"  {dl.name}", ""])  # Second column empty (slider goes there)
            item.setData(0, _ROLE, ("_data_layer", dl.id))
            item.setCheckState(
                0,
                Qt.CheckState.Checked if dl.visible else Qt.CheckState.Unchecked,
            )
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            self._data_tree.addTopLevelItem(item)
            
            # Add opacity slider in second column
            opacity_slider = QSlider(Qt.Orientation.Horizontal)
            opacity_slider.setMinimum(0)
            opacity_slider.setMaximum(100)
            opacity_value = int(getattr(dl, "opacity", 1.0) * 100)
            opacity_slider.setValue(opacity_value)
            opacity_slider.setToolTip(f"{opacity_value}%")
            # Use lambda to capture dl.id for the signal
            opacity_slider.valueChanged.connect(
                lambda value, layer_id=dl.id: self._on_opacity_changed(layer_id, value)
            )
            self._data_tree.setItemWidget(item, 1, opacity_slider)
            
        self._data_tree.blockSignals(False)

    def _on_opacity_changed(self, layer_id: str, value: int) -> None:
        """Called when an opacity slider is moved."""
        opacity = value / 100.0
        # Update tooltip on the slider
        for i in range(self._data_tree.topLevelItemCount()):
            item = self._data_tree.topLevelItem(i)
            if item is None:
                continue
            data = item.data(0, _ROLE)
            if data and data[0] == "_data_layer" and data[1] == layer_id:
                slider = self._data_tree.itemWidget(item, 1)
                if slider:
                    slider.setToolTip(f"{value}%")
                break
        self.data_layer_opacity_changed.emit(layer_id, opacity)

    def select_element(self, element_type: str, element_id: str) -> None:
        """Programmatically highlight an element row in the tree."""
        if not element_type or not element_id:
            self._tree.clearSelection()
            self._tree.setCurrentItem(None)
            return
        for i in range(self._tree.topLevelItemCount()):
            layer_item = self._tree.topLevelItem(i)
            if layer_item is None:
                continue
            for j in range(layer_item.childCount()):
                child = layer_item.child(j)
                d = child.data(0, _ROLE) if child else None
                if d and d[0] == element_type and d[1] == element_id:
                    self._tree.setCurrentItem(child)
                    return


    def _on_item_clicked(self, item: QTreeWidgetItem | None, _column: int) -> None:
        if item is None:
            return
        data = item.data(0, _ROLE)
        if data and data[0] not in ("_layer",):
            etype, eid = data
            self.element_selected.emit(etype, eid)

    def _on_data_item_changed(self, item: QTreeWidgetItem | None, _column: int) -> None:
        if item is None:
            return
        data = item.data(0, _ROLE)
        if not data or data[0] != "_data_layer":
            return
        visible = item.checkState(0) == Qt.CheckState.Checked
        self.data_layer_visibility_changed.emit(data[1], visible)

    def _on_data_layer_context_menu(self, pos) -> None:
        """Right-click menu on a data layer item to edit the underlying data source."""
        item = self._data_tree.itemAt(pos)
        if item is None:
            return
        d = item.data(0, _ROLE)
        if not d or d[0] != "_data_layer":
            return
        dl_id = d[1]
        # Resolve the source_id from the project (dl.id == dl_id, dl.source_id is what we need)
        source_id = None
        if self._project:
            for dl in getattr(self._project, "data_layers", []):
                if dl.id == dl_id:
                    source_id = dl.source_id
                    break
        if not source_id:
            return
        menu = QMenu(self)
        act_edit = menu.addAction(t("✏  Edit Source…"))
        chosen = menu.exec(self._data_tree.mapToGlobal(pos))
        if chosen == act_edit:
            self.data_layer_edit_requested.emit(source_id)

    def _on_item_changed(self, item: QTreeWidgetItem | None, _column: int) -> None:
        if item is None:
            return
        data = item.data(0, _ROLE)
        if not data:
            return
        kind, id_or_name = data
        visible = item.checkState(0) == Qt.CheckState.Checked
        if kind == "_layer":
            self.layer_visibility_changed.emit(id_or_name, visible)
        else:
            self.element_visibility_changed.emit(kind, id_or_name, visible)

    def _on_remove_layer(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        # Navigate to the top-level layer item if a child is selected
        parent = item.parent()
        if parent is not None:
            item = parent
        data = item.data(0, _ROLE)
        if not data or data[0] != "_layer":
            return
        layer_name = data[1]
        if layer_name == "Default":
            QMessageBox.warning(self, "Cannot Remove", "The 'Default' layer cannot be removed.")
            return
        self.layer_remove_requested.emit(layer_name)

    def _on_context_menu(self, pos) -> None:
        """Right-click context menu for layers (remove) and elements (go_to/edit/remove/update)."""
        item = self._tree.itemAt(pos)
        if item is None:
            return
        d = item.data(0, _ROLE)
        if not d:
            return
        menu = QMenu(self)
        if d[0] == "_layer":
            layer_name = d[1]
            act_remove = menu.addAction(t("🗑  Remove Layer…"))
            chosen = menu.exec(self._tree.mapToGlobal(pos))
            if chosen == act_remove:
                if layer_name == "Default":
                    QMessageBox.warning(self, t("Cannot Remove"),
                                        t("The 'Default' layer cannot be removed."))
                    return
                self.layer_remove_requested.emit(layer_name)
        else:
            etype, eid = d
            act_goto   = menu.addAction(t("🎯  Go to"))
            act_edit   = menu.addAction(t("✏  Edit…"))
            act_update = menu.addAction(t("🔄  Update"))
            menu.addSeparator()
            act_remove = menu.addAction(t("🗑  Remove…"))
            chosen = menu.exec(self._tree.mapToGlobal(pos))
            if chosen == act_goto:
                self.element_action_requested.emit("go_to", etype, eid)
            elif chosen == act_edit:
                self.element_action_requested.emit("edit", etype, eid)
            elif chosen == act_update:
                self.element_action_requested.emit("update", etype, eid)
            elif chosen == act_remove:
                self.element_action_requested.emit("remove", etype, eid)

    def _on_export_csv(self) -> None:
        """Export elements of the currently selected layer to CSV."""
        item = self._tree.currentItem()
        if item is None:
            QMessageBox.information(self, "No Selection", "Select a layer first.")
            return
        parent = item.parent()
        if parent is not None:
            item = parent
        data = item.data(0, _ROLE)
        if not data or data[0] != "_layer":
            QMessageBox.information(self, "No Layer", "Select a layer node to export.")
            return
        self._export_layer_csv(data[1])

    def _export_layer_csv(self, layer_name: str) -> None:
        if self._project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export '{layer_name}' to CSV",
            f"{layer_name}.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return

        # Collect all visible metadata keys across elements in this layer
        all_meta_keys: set[str] = set()
        for zone in self._project.zones:
            if getattr(zone, "layer", "Default") == layer_name:
                hidden = set(getattr(zone, "metadata_hidden", []))
                for k in zone.metadata:
                    if k not in hidden and not k.startswith("__"):
                        all_meta_keys.add(k)
        for kp in self._project.keypoints:
            if getattr(kp, "layer", "Default") == layer_name:
                hidden = set(getattr(kp, "metadata_hidden", []))
                for k in kp.metadata:
                    if k not in hidden and not k.startswith("__"):
                        all_meta_keys.add(k)

        meta_keys = sorted(all_meta_keys)
        base_fields = ["type", "id", "name", "lat", "lon", "layer",
                       "zone_type", "radius_m", "width_m", "height_m", "rotation_deg"]
        _DERIVED = ["area_m2", "perimeter_m", "centroid_lat", "centroid_lon", "vertex_count"]
        all_fields = base_fields + _DERIVED + meta_keys

        rows: list[dict[str, object]] = []

        for zone in self._project.zones:
            if getattr(zone, "layer", "Default") != layer_name:
                continue
            coords = zone.coordinates
            if coords:
                lat = round(sum(c.lat for c in coords) / len(coords), 7)
                lon = round(sum(c.lon for c in coords) / len(coords), 7)
            else:
                lat = lon = ""
            hidden = set(getattr(zone, "metadata_hidden", []))
            row: dict = {
                "type": "zone",
                "id": str(zone.id),
                "name": zone.name,
                "lat": lat,
                "lon": lon,
                "layer": layer_name,
                "zone_type": zone.zone_type,
                "radius_m": zone.radius_m if zone.zone_type == "circle" else "",
                "width_m": zone.width_m or "",
                "height_m": zone.height_m or "",
                "rotation_deg": zone.rotation_deg if zone.rotation_deg else "",
            }
            for dk in _DERIVED:
                row[dk] = zone.metadata.get(dk, "")
            for k in meta_keys:
                row[k] = zone.metadata.get(k, "") if k not in hidden else ""
            rows.append(row)

        for kp in self._project.keypoints:
            if getattr(kp, "layer", "Default") != layer_name:
                continue
            hidden = set(getattr(kp, "metadata_hidden", []))
            row = {
                "type": "keypoint",
                "id": str(kp.id),
                "name": kp.info_card.title or kp.name,
                "lat": round(kp.lat, 7),
                "lon": round(kp.lon, 7),
                "layer": layer_name,
                "zone_type": "", "radius_m": "", "width_m": "", "height_m": "", "rotation_deg": "",
            }
            for dk in _DERIVED:
                row[dk] = ""
            for k in meta_keys:
                row[k] = kp.metadata.get(k, "") if k not in hidden else ""
            rows.append(row)

        for ann in self._project.annotations:
            if getattr(ann, "layer", "Default") != layer_name:
                continue
            rows.append({
                "type": "annotation",
                "id": str(getattr(ann, "id", "")),
                "name": ann.content[:60],
                "lat": ann.anchor_lat or "",
                "lon": ann.anchor_lon or "",
                "layer": layer_name,
                "zone_type": "", "radius_m": "", "width_m": "", "height_m": "", "rotation_deg": "",
                **{dk: "" for dk in _DERIVED},
                **{k: "" for k in meta_keys},
            })

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=all_fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return

        QMessageBox.information(
            self, "CSV Exported", f"Exported {len(rows)} element(s) to:\n{path}"
        )

