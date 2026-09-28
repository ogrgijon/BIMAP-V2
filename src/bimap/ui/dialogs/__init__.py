"""Dialogs package."""

from bimap.ui.dialogs.data_source_dialog import DataSourceDialog
from bimap.ui.dialogs.delimitation_dialog import DelimitationDialog
from bimap.ui.dialogs.element_edit_dialog import ElementEditDialog
from bimap.ui.dialogs.export_dialog import ExportDialog
from bimap.ui.dialogs.extension_editor_dialog import ExtensionEditorDialog
from bimap.ui.dialogs.extension_manager_dialog import ExtensionManagerDialog
from bimap.ui.dialogs.extension_viewer_dialog import ExtensionViewerDialog
from bimap.ui.dialogs.geocode_dialog import GeocodeDialog
from bimap.ui.dialogs.live_layer_dialog import LiveLayerDialog
from bimap.ui.dialogs.map_composer_dialog import MapComposerDialog
from bimap.ui.dialogs.metadata_view_dialog import MetadataViewDialog

__all__ = [
    "DataSourceDialog",
    "DelimitationDialog",
    "ElementEditDialog",
    "ExportDialog",
    "ExtensionEditorDialog",
    "ExtensionManagerDialog",
    "ExtensionViewerDialog",
    "GeocodeDialog",
    "LiveLayerDialog",
    "MapComposerDialog",
    "MetadataViewDialog",
]
