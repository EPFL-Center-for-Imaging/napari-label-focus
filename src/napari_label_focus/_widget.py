from typing import Callable, Dict, List, Optional

import napari

import napari.layers
import numpy as np
import pandas as pd
from napari.utils.notifications import show_info
from napari_toolkit.containers.collapsible_groupbox import QCollapsibleGroupBox
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
    QPushButton,
    QFileDialog,
    QSizePolicy,
)

from napari_label_focus._context import SelectionContext
from napari_label_focus._events import default_table_click_event
from napari_label_focus._utils import (
    color_labels_layer_by_values,
    sanitize_layer_features,
)

from napari_label_focus._featurizer import FeaturizerWidget


# Selected colormaps from Matplotlib (https://matplotlib.org/stable/users/explain/colors/colormaps.html)
# We avoid colormaps with black values as they get rendered weirdly.
COLORMAPS = [
    "viridis",
    "plasma",
    "cividis",
    "coolwarm",
    "jet",
    "Reds",
    "Greens",
    "Blues",
    "random",  # Specially handled (not a matplotlib colormap)
]


class PropsUIStore:
    def __init__(self) -> None:
        """This object is used to keep track of the selected table and labels display parameters, for each layer."""
        # The `state` maps napari layers to selected UI values (`color by`, etc.) for these layers
        self.state: Dict[napari.layers.Layer, Dict] = {}

    def ensure_registered(self, layer: napari.layers.Layer) -> Dict:
        if layer in self.state:
            return self.state[layer]
        else:
            return self.register_new_layer(layer)

    def register_new_layer(self, layer: napari.layers.Layer) -> Dict:
        default_props = {
            "props_ui": {},
            "sort_by": "",
            "color_by": "",
            "colormap": COLORMAPS[0],
            "ascending": False,
        }
        self.state[layer] = default_props
        return default_props

    def layer_features_df(self, layer: napari.layers.Layer) -> pd.DataFrame:
        props = self.ensure_registered(layer)

        features_df = sanitize_layer_features(layer)

        if len(features_df.columns) > 0:
            # Sort the dataframe
            sort_by = props["sort_by"]
            ascending = props["ascending"]
            if sort_by in features_df.columns:
                features_df.sort_values(by=sort_by, ascending=ascending, inplace=True)

            # Filter columns to show
            props_ui = props["props_ui"]
            columns_to_show = []
            for k, v in props_ui.items():
                if (v.isChecked()) & (k in features_df.columns):
                    columns_to_show.append(k)

            return features_df[columns_to_show]
        else:
            return features_df

    def get_ascending(self, layer: napari.layers.Layer) -> Optional[bool]:
        props = self.ensure_registered(layer)
        return props.get("ascending")

    def set_ascending(self, layer: napari.layers.Layer, ascending: bool):
        self.ensure_registered(layer)
        self.state[layer]["ascending"] = ascending

    def get_sort_by(self, layer: napari.layers.Layer) -> Optional[str]:
        props = self.ensure_registered(layer)
        return props.get("sort_by")

    def set_sort_by(self, layer: napari.layers.Layer, sort_by: str):
        self.ensure_registered(layer)
        self.state[layer]["sort_by"] = sort_by

    def get_color_by(self, layer: napari.layers.Layer) -> Optional[str]:
        props = self.ensure_registered(layer)
        return props.get("color_by")

    def set_color_by(self, layer: napari.layers.Layer, color_by: str):
        self.ensure_registered(layer)
        self.state[layer]["color_by"] = color_by

    def get_colormap(self, layer: napari.layers.Layer) -> Optional[str]:
        props = self.ensure_registered(layer)
        return props.get("colormap")

    def set_colormap(self, layer: napari.layers.Layer, colormap: str):
        self.ensure_registered(layer)
        self.state[layer]["colormap"] = colormap

    def get_prop_ui(self, layer: napari.layers.Layer, prop: str) -> Optional[QCheckBox]:
        props = self.ensure_registered(layer)
        return props["props_ui"].get(prop)

    def set_prop_ui(
        self, layer: napari.layers.Layer, prop: str, prop_checkbox: QCheckBox
    ):
        self.ensure_registered(layer)
        self.state[layer]["props_ui"][prop] = prop_checkbox

    def get_color_by_col_idx(self, layer: napari.layers.Layer) -> Optional[int]:
        features_df = sanitize_layer_features(layer)
        color_by = self.get_color_by(layer)
        if color_by in features_df.columns:
            for col_idx, col in enumerate(features_df.columns):
                if col == color_by:
                    return col_idx

    def get_colormap_col_idx(self, layer: napari.layers.Layer) -> Optional[int]:
        colormap = self.get_colormap(layer)
        for col_idx, col in enumerate(COLORMAPS):
            if col == colormap:
                return col_idx

    def get_sort_by_col_idx(self, layer: napari.layers.Layer) -> Optional[int]:
        features_df = sanitize_layer_features(layer)
        sort_by = self.get_sort_by(layer)
        if sort_by in features_df.columns:
            for col_idx, col in enumerate(features_df.columns):
                if col == sort_by:
                    return col_idx


def _reset_table(table: QTableWidget) -> QTableWidget:
    """Utility function to reset a QTableWidget."""
    table.clear()
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setColumnCount(1)
    table.setRowCount(1)
    table.setVisible(False)
    return table


class ConfigurableFeaturesTableWidget(QWidget):
    def __init__(
        self,
        napari_viewer: napari.Viewer,
        table_click_callbacks: Optional[
            List[Callable[[SelectionContext], None]]
        ] = None,
        featurizer_functs: Optional[List[Callable[[np.ndarray], pd.DataFrame]]] = None,
    ):
        """
        Configurable features table widget for Napari.

        :param table_click_callabacks: A list of functions to call when a row in the table is clicked. Callback functions receive the selection context as input.
        :param featurizer_functs: A list of functions that compute features on Labels layers. Called the first time a Labels layer is selected, and when the labels data changes.
        """
        super().__init__()
        self.viewer = napari_viewer

        # The "Featurizer widget" has no layout of itself, but it connects viewer events and manages recomputing features.
        featurizer_widget = FeaturizerWidget(
            napari_viewer=napari_viewer,
            featurizer_functs=featurizer_functs,
        )

        # The "Props UI store" stores and allows to retreive display choices for all napari layers
        self.props_ui_store = PropsUIStore()

        # Keep track of the selected layer
        self.selected_layer = None

        ### Configurable table click events ###
        self.table_click_callbacks = [default_table_click_event]
        if table_click_callbacks is not None:
            self.table_click_callbacks.extend(table_click_callbacks)  # type: ignore

        # Create the layout
        self.setLayout(QGridLayout())

        # `Color by` = Hue of the selected labels layer
        self.layout().addWidget(QLabel("Color by", self), 0, 0)  # type: ignore
        self.color_by_cb = QComboBox()
        self.layout().addWidget(self.color_by_cb, 0, 1)  # type: ignore
        self.color_by_cb.currentTextChanged.connect(self._color_changed)

        # Colormap selection
        self.layout().addWidget(QLabel("Colormap", self), 0, 2)  # type: ignore
        self.colormap_cb = QComboBox()
        self.colormap_cb.addItems(COLORMAPS)
        self.layout().addWidget(self.colormap_cb, 0, 3)  # type: ignore
        self.colormap_cb.currentTextChanged.connect(self._colormap_changed)
        
        # --- Table --- #
        
        # Sort table
        self.layout().addWidget(QLabel("Sort by", self), 1, 0)  # type: ignore
        self.sort_by_cb = QComboBox()
        self.layout().addWidget(self.sort_by_cb, 1, 1)  # type: ignore
        self.sort_by_cb.currentTextChanged.connect(self._sort_changed)
        self.layout().addWidget(QLabel("Ascending", self), 1, 2)  # type: ignore
        self.sort_ascending = QCheckBox()
        self.sort_ascending.setChecked(False)
        self.sort_ascending.toggled.connect(self._ascending_changed)
        self.layout().addWidget(self.sort_ascending, 1, 3)  # type: ignore

        # Show properties
        self.show_props_gb = QCollapsibleGroupBox("Show properties")  # type: ignore
        self.show_props_gb.setChecked(False)
        self.sp_layout = QGridLayout(self.show_props_gb)
        self.layout().addWidget(self.show_props_gb, 2, 0, 1, 4)  # type: ignore

        # Table
        self.table = _reset_table(QTableWidget())
        self.table.clicked.connect(self._table_clicked)
        # TODO: Make the table expansible
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout().addWidget(self.table, 3, 0, 1, 4)  # type: ignore

        # Save as CSV button
        save_button = QPushButton("Save as CSV")
        save_button.clicked.connect(self._save_csv)
        self.layout().addWidget(save_button, 4, 0, 1, 4)  # type: ignore

        # ------------- #
        
        # Layer events
        self.viewer.layers.selection.events.changed.connect(
            self._layer_selection_changed
        )
        self.viewer.layers.events.inserted.connect(
            lambda e: self._layer_selection_changed(None)
        )
        self._layer_selection_changed(None)
        
        # ------------- #
        
    def _save_csv(self, e):
        layer = self.selected_layer
        if layer is not None:
            df = self.props_ui_store.layer_features_df(layer)
            if df is not None:
                filename, _ = QFileDialog.getSaveFileName(
                    self, "Save as CSV", ".", "*.csv"
                )
                df.to_csv(filename)
                show_info(f"Saved: {filename}")

    ### Callbacks that lead to updating the table UI (layer selection change, features change, selected label change) ###

    def _layer_selection_changed(self, event):
        if event is None:
            layer = self.viewer.layers.selection.active
        else:
            layer = event.source.active

        if isinstance(self.selected_layer, napari.layers.Labels):
            # Features changed or label changed *while the layer is selected* should update the UI
            self.selected_layer.events.features.disconnect(self._features_changed)
            self.selected_layer.events.selected_label.disconnect(
                self._selected_label_changed
            )

        if isinstance(layer, napari.layers.Labels):
            layer.events.features.connect(self._features_changed)
            layer.events.selected_label.connect(self._selected_label_changed)

        self.selected_layer = layer

        self.update_table_ui(layer)

    def _selected_label_changed(self, event):
        layer = event.sources[0]
        if not isinstance(layer, napari.layers.Labels):
            return
        self._update_table_layout(layer)

    def _features_changed(self, event):
        layer = event.sources[0]
        if not isinstance(layer, napari.layers.Labels):
            return
        self.update_table_ui(layer)

    ### UPDATE TABLE UI => Fills values for all display parameter comboboxes, etc. + redraws the table ###

    def update_table_ui(self, layer: Optional[napari.layers.Layer]) -> None:
        if layer is None:
            return

        # Update sort dropdown
        self._update_sort_cb(layer)

        # Update color dropdown
        self._update_color_cb(layer)

        # Update colormap dropdown
        self._update_colormap_cb(layer)

        # Update ascending state
        self._update_ascending_checkbox(layer)

        # Update visible properties
        self._update_visible_props_layout(layer)
        
        # Sort and update table
        self._update_table_layout(layer)

    ### Events triggered by "update table UI" (update sort, color by comboboxes, etc.) ###

    def _update_sort_cb(self, layer: napari.layers.Layer):
        col_idx = self.props_ui_store.get_sort_by_col_idx(layer)

        self.sort_by_cb.clear()

        df_features = sanitize_layer_features(layer)

        if len(df_features.columns) > 0:
            self.sort_by_cb.addItems(df_features.columns)

        if col_idx:
            self.sort_by_cb.setCurrentIndex(col_idx)

    def _update_color_cb(self, layer: napari.layers.Layer):
        col_idx = self.props_ui_store.get_color_by_col_idx(layer)

        self.color_by_cb.clear()

        df_features = sanitize_layer_features(layer)

        if len(df_features.columns) > 0:
            self.color_by_cb.addItems(df_features.columns)

        if col_idx is not None:
            self.color_by_cb.setCurrentIndex(col_idx)

    def _update_colormap_cb(self, layer: napari.layers.Layer):
        colormap_idx = self.props_ui_store.get_colormap_col_idx(layer)
        if colormap_idx is not None:
            self.colormap_cb.setCurrentIndex(colormap_idx)

    def _update_ascending_checkbox(self, layer: napari.layers.Layer):
        ascending = self.props_ui_store.get_ascending(layer)
        if ascending:
            self.sort_ascending.setChecked(ascending)

    def _update_visible_props_layout(self, layer: napari.layers.Layer):
        # Clear the existing props layout
        for i in reversed(range(self.sp_layout.count())):
            ui_item = self.sp_layout.itemAt(i)
            if ui_item is not None:
                ui_item_widget = ui_item.widget()
                if ui_item_widget is not None:
                    ui_item_widget.setParent(None)

        df_features = sanitize_layer_features(layer)

        # Populate the props layout
        if len(df_features.columns) > 0:
            for idx, prop in enumerate(df_features.columns):
                self.sp_layout.addWidget(QLabel(prop, self), idx, 0)

                prop_checkbox = self.props_ui_store.get_prop_ui(layer, prop)

                if prop_checkbox is None:
                    # Initialize a new checkbox component
                    prop_checkbox = QCheckBox()
                    prop_checkbox.setChecked(True)
                    prop_checkbox.toggled.connect(self._prop_checkbox_toggled)
                prop_checkbox.setVisible(True)

                self.sp_layout.addWidget(prop_checkbox, idx, 1)

                self.props_ui_store.set_prop_ui(layer, prop, prop_checkbox)

    ### Update table layout ###

    def _update_table_layout(self, layer: napari.layers.Layer):
        df_filtered = self.props_ui_store.layer_features_df(layer)

        n_rows = len(df_filtered)
        n_cols = len(df_filtered.columns)

        # Update the table UI
        self.table.setVisible(True)
        self.table.setRowCount(n_rows)
        self.table.setColumnCount(n_cols)
        for icol, col in enumerate(df_filtered.columns):
            self.table.setHorizontalHeaderItem(icol, QTableWidgetItem(col))

        # Fill the Qtable with dataframe values
        for i, col in enumerate(df_filtered.columns):
            vals = df_filtered[col].values
            for k, val in enumerate(vals):
                self.table.setItem(k, i, QTableWidgetItem(str(val)))

        if isinstance(layer, napari.layers.Labels):
            if "label" in df_filtered.columns:
                selected_label = layer.selected_label
                # Select the table row if specified
                if selected_label is not None:
                    for k, val in enumerate(df_filtered["label"].values):
                        if val == selected_label:
                            self.table.selectRow(k)

    ### Callbacks that trigger update table layout (sort changes, ascending changes, etc.) ###

    def _prop_checkbox_toggled(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        self._update_table_layout(self.selected_layer)

    def _sort_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        sort_by = self.sort_by_cb.currentText()
        if sort_by == "":
            return

        self.props_ui_store.set_sort_by(self.selected_layer, sort_by)
        self._update_table_layout(self.selected_layer)

    def _ascending_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        ascending = self.sort_ascending.isChecked()
        self.props_ui_store.set_ascending(self.selected_layer, ascending)
        self._update_table_layout(self.selected_layer)

    ### Callbacks that trigger a color change in the Labels layer ###

    def _color_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        color_by = self.color_by_cb.currentText()
        if color_by == "":
            return

        colormap = self.props_ui_store.get_colormap(self.selected_layer)
        if (colormap is None) or (colormap == ""):
            return

        self.props_ui_store.set_color_by(self.selected_layer, color_by)

        color_labels_layer_by_values(
            self.selected_layer,
            self.selected_layer.features,
            color_by,
            colormap=colormap,
        )

    def _colormap_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        color_by = self.props_ui_store.get_color_by(self.selected_layer)
        if (color_by is None) or (color_by == ""):
            return

        colormap = self.colormap_cb.currentText()
        if colormap == "":
            return

        self.props_ui_store.set_colormap(self.selected_layer, colormap)

        color_labels_layer_by_values(
            self.selected_layer,
            self.selected_layer.features,
            color_by,
            colormap=colormap,
        )

    ### Callback on table click (configurable) ###

    def _table_clicked(self):
        selected_table_idx = self.table.currentRow()

        if self.selected_layer is None:
            return

        features_df = sanitize_layer_features(self.selected_layer)

        if len(features_df) == 0:
            return

        selection_context = SelectionContext(
            viewer=self.viewer,
            selected_layer=self.selected_layer,
            selected_table_idx=selected_table_idx,
            features_table=features_df,
        )

        for func in self.table_click_callbacks:
            func(selection_context)
