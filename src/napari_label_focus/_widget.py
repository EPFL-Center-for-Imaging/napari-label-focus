from collections import defaultdict
from typing import Callable, Dict, List, Optional

import napari
import napari.layers
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from napari.utils.notifications import show_warning, show_info
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
)

from napari_label_focus._context import SelectionContext
from napari_label_focus._events import default_table_click_event
from napari_label_focus._featurizers import default_featurizer


def _color_labels_layer_by_values(layer: napari.layers.Labels, features_df: pd.DataFrame, color_by: str):
    from napari.utils import DirectLabelColormap

    plot_vals = features_df[color_by].values
    relative_vals = (plot_vals - plot_vals.min()) / plot_vals.max()  # [0-1]
    
    cmap = plt.get_cmap("inferno")
    rgba = cmap(relative_vals)
    
    color_dict = defaultdict(lambda: np.zeros(4))
    for lab, color in zip(features_df["label"].values, rgba):
        color_dict[lab] = color

    layer.events.selected_label.block()
    layer.colormap = DirectLabelColormap(color_dict=color_dict)
    layer.events.selected_label.unblock()
    layer.refresh()


def _sync_table_ui_with_selection_meta(
    table: QTableWidget, table_ctx: Dict, selected_label: Optional[int] = None
) -> None:
    df = table_ctx["df"]
    if df is None:
        _reset_table(table)
        return

    sort_by = table_ctx["sort_by"]
    ascending = table_ctx["ascending"]
    props_ui = table_ctx["props_ui"]

    # Sort the dataframe
    if sort_by in df.columns:
        df.sort_values(by=sort_by, ascending=ascending, inplace=True)

    # Filter columns to show
    columns_to_show = []
    for k, v in props_ui.items():
        if (v.isChecked()) & (k in df.columns):
            columns_to_show.append(k)
    df_filtered = df[columns_to_show]

    # Update the table UI
    table.setVisible(True)
    table.setRowCount(len(df_filtered))
    table.setColumnCount(len(df_filtered.columns))
    for icol, col in enumerate(df_filtered.columns):
        table.setHorizontalHeaderItem(icol, QTableWidgetItem(col))
    for k, (_, row) in enumerate(df_filtered.iterrows()):
        for i, col in enumerate(row.index):
            val = str(row[col])
            table.setItem(k, i, QTableWidgetItem(val))
            # Highlight the table row with selected label
            try:
                val_parsed = int(float(val))
            except ValueError:
                # val is probably NaN
                continue
            if (
                (selected_label is not None)
                & (col == "label")
                & (val_parsed == selected_label)
            ):
                table.selectRow(k)


def _reset_table(table: QTableWidget) -> QTableWidget:
    table.clear()
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setColumnCount(1)
    table.setRowCount(1)
    table.setVisible(False)
    return table


def _merge_incoming_df(
    df_incoming: pd.DataFrame, df_existing: pd.DataFrame
) -> pd.DataFrame:
    # Shared columns that are not "label"
    shared_cols = df_incoming.columns.intersection(df_existing.columns).difference(
        ["label"]
    )

    # Left merge to keep only label rows present in the incoming features
    df_merged = df_incoming.merge(
        df_existing, on="label", how="left", suffixes=("_incoming", "_existing")
    )

    # Overwrite existing values with incoming values
    for col in shared_cols:
        df_merged[col] = df_merged[f"{col}_incoming"]

    # Drop all suffixed columns
    cols_to_drop = [f"{col}_incoming" for col in shared_cols] + [
        f"{col}_existing" for col in shared_cols
    ]
    df_merged = df_merged.drop(columns=cols_to_drop)
    
    return df_merged


def _compute_features_df(
    labels_layer: napari.layers.Labels,
    featurizer_funcs: Optional[List[Callable[[np.ndarray], pd.DataFrame]]] = None,
) -> Optional[pd.DataFrame]:
    """
    Performs checks to sanitize a labels layer and its data, then computes and updates its features table from the provided featurizer functions.
    """
    # Sanitize existing features
    features = labels_layer.features
    if not isinstance(features, (pd.DataFrame, type(None))):
        show_warning("Existing features should be in DataFrame format (or None)")
        return
    if isinstance(features, pd.DataFrame):
        if len(features) > 0:
            if not ("label" in features.columns):
                show_warning("Existing features have no 'label' column")
                return

    # Sanitize labels layer data
    labels = labels_layer.data
    if not isinstance(labels, np.ndarray):
        show_warning("Labels data should be a Numpy array")
        return

    if labels.ndim not in [2, 3]:
        show_warning("Labels data should be 2D or 3D")
        return

    if labels.sum() == 0:
        show_warning("Labels data are only zero")
        return

    # Extract features from default and extra featurizers
    features_df = default_featurizer(labels)
    if featurizer_funcs is not None:
        for func in featurizer_funcs:
            features_df = _merge_incoming_df(func(labels), features_df)
            

    # Sanitize computed features
    if not ("label" in features_df.columns):
        show_warning("Features DataFrame should have a 'label' column")
        return

    # Merge computed features into existing ones
    if (features is None) | (len(features) == 0):
        df_merged = features_df
    else:
        df_merged = _merge_incoming_df(features_df, features)

    # Update the layer features
    labels_layer.features = df_merged

    return df_merged


class ConfigurableFeaturesTableWidget(QWidget):
    def __init__(
        self,
        napari_viewer: napari.Viewer,
        table_click_callbacks: Optional[
            List[Callable[[SelectionContext], None]]
        ] = None,
        featurizers: Optional[List[Callable[[np.ndarray], pd.DataFrame]]] = None,
    ):
        """
        Configurable features table widget for Napari.

        :param table_click_events: A list of functions to call when a row in the table is clicked. Callback functions receive the selection context as input.
        :param featurizers: A list of functions that compute features on Labels layers. Called the first time a Labels layer is selected, and when the labels data changes.
        """
        super().__init__()
        self.viewer = napari_viewer

        self.selected_layer: Optional[napari.layers.Layer] = None
        self.state = {}

        self.setLayout(QGridLayout())

        ### Configurable table click events ###
        self.table_click_callbacks = [default_table_click_event]
        if table_click_callbacks is not None:
            for func in table_click_callbacks:
                self.table_click_callbacks.append(func)
        ### ------------------ ###

        ### Configurable featurizer functions ###
        self.featurizers = []
        if featurizers is not None:
            for func in featurizers:
                self.featurizers.append(func)
        ### ------------------ ###

        # Sort table
        self.layout().addWidget(QLabel("Sort by", self), 0, 0)
        self.sort_by_cb = QComboBox()
        self.layout().addWidget(self.sort_by_cb, 0, 1)
        self.sort_by_cb.currentTextChanged.connect(self._sort_changed)
        self.layout().addWidget(QLabel("Ascending", self), 0, 2)
        self.sort_ascending = QCheckBox()
        self.sort_ascending.setChecked(True)
        self.sort_ascending.toggled.connect(self._ascending_changed)
        self.layout().addWidget(self.sort_ascending, 0, 3)
        
        # `Color by` = Hue of the selected labels layer
        self.layout().addWidget(QLabel("Color by", self), 1, 0)
        self.color_by_cb = QComboBox()
        self.layout().addWidget(self.color_by_cb, 1, 1)
        self.color_by_cb.currentTextChanged.connect(self._color_changed)

        # Show properties
        self.show_props_gb = QCollapsibleGroupBox("Show properties")
        self.show_props_gb.setChecked(False)
        self.sp_layout = QGridLayout(self.show_props_gb)
        self.layout().addWidget(self.show_props_gb, 2, 0, 1, 4)

        # Table
        self.table = _reset_table(QTableWidget())
        self.table.clicked.connect(self._clicked_table)
        # TODO: Create an expansible layout for the table...
        self.layout().addWidget(self.table, 3, 0, 1, 4)
        
        # Save as CSV button
        save_button = QPushButton("Save as CSV")
        save_button.clicked.connect(self._save_csv)
        self.layout().addWidget(save_button, 4, 0, 1, 4)

        # Layer events
        self.viewer.layers.selection.events.changed.connect(
            self._layer_selection_changed
        )
        self.viewer.layers.events.inserted.connect(
            lambda e: self._layer_selection_changed(None)
        )
        self._layer_selection_changed(None)

    def _initialize_new_selected_layer(self, selected_layer: napari.layers.Layer):
        # Register the new layer to the `state` (seen layers)
        self.state[self.selected_layer] = {
            "props_ui": {},
            "sort_by": None,
            "color_by": None,
            "ascending": self.sort_ascending.isChecked(),
            "df": None,
        }

        if isinstance(self.selected_layer, napari.layers.Labels):
            self.selected_layer.events.paint.disconnect(self._update_labels_df)
            self.selected_layer.events.data.disconnect(self._update_labels_df)
            # self.selected_layer.events.features.disconnect(self._update_labels_df)
            self.selected_layer.events.selected_label.disconnect(
                self._selected_label_changed
            )

        if isinstance(selected_layer, napari.layers.Labels):
            selected_layer.events.data.connect(self._update_labels_df)
            selected_layer.events.paint.connect(self._update_labels_df)
            # selected_layer.events.features.connect(self._update_labels_df)
            selected_layer.events.selected_label.connect(self._selected_label_changed)

    def _save_csv(self, e):
        selection_meta = self.state[self.selected_layer]
        df = selection_meta.get("df")
        if df is None:
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Save as CSV", ".", "*.csv")
        df.to_csv(filename)
        show_info(f"Saved: {filename}")
    
    def _selected_label_changed(self, event):
        layer = event.sources[0]
        if isinstance(layer, napari.layers.Labels):
            selection_meta = self.state[self.selected_layer]
            _sync_table_ui_with_selection_meta(
                self.table, selection_meta, selected_label=layer.selected_label
            )

    def _layer_selection_changed(self, event):
        if event is None:
            selected_layer = self.viewer.layers.selection.active
        else:
            selected_layer = event.source.active

        self.selected_layer = selected_layer

        if self.selected_layer in self.state:
            # Skip recomputing the features
            self.update_table_ui()
        else:
            self._initialize_new_selected_layer(selected_layer)
            self._update_labels_df()

    def _update_labels_df(self):
        if isinstance(self.selected_layer, napari.layers.Labels):
            self.state[self.selected_layer]["df"] = _compute_features_df(
                labels_layer=self.selected_layer,
                featurizer_funcs=self.featurizers,
            )
        self.update_table_ui()

    def update_table_ui(self) -> None:
        # Get the layer's associated data from the `state`
        selection_meta = self.state[self.selected_layer]

        # Update sort dropdown
        self._update_sort_cb(selection_meta)
        
        # Update color dropdown
        self._update_color_cb(selection_meta)

        # Update ascending state
        self._update_ascending_checkbox(selection_meta)

        # Update visible properties
        self._update_visible_props_layout(selection_meta)

        # Sort and update table
        self._update_table_layout()

    def _update_ascending_checkbox(self, selection_meta):
        self.sort_ascending.setChecked(selection_meta["ascending"])

    def _update_sort_cb(self, selection_meta):
        self.sort_by_cb.clear()
        if selection_meta.get("df") is not None:
            self.sort_by_cb.addItems(selection_meta["df"].columns)
        if selection_meta.get("sort_by") is not None:
            for col_idx, col in enumerate(selection_meta["df"].columns):
                if col == selection_meta["sort_by"]:
                    self.sort_by_cb.setCurrentIndex(col_idx)
    
    def _update_color_cb(self, selection_meta):
        self.color_by_cb.clear()
        if selection_meta.get("df") is not None:
            self.color_by_cb.addItems(selection_meta["df"].columns)
        if selection_meta.get("color_by") is not None:
            for col_idx, col in enumerate(selection_meta["df"].columns):
                if col == selection_meta["color_by"]:
                    self.color_by_cb.setCurrentIndex(col_idx)

    def _update_visible_props_layout(self, selection_meta):
        # Clear the existing props layout
        for i in reversed(range(self.sp_layout.count())):
            ui_item = self.sp_layout.itemAt(i)
            if ui_item is not None:
                ui_item_widget = ui_item.widget()
                if ui_item_widget is not None:
                    ui_item_widget.setParent(None)

        # Populate the props layout
        visible_props_ui = {}
        if selection_meta.get("df") is not None:
            for idx, prop in enumerate(selection_meta["df"].columns):
                self.sp_layout.addWidget(QLabel(prop, self), idx, 0)
                if selection_meta.get("props_ui").get(prop) is not None:
                    # Reuse the existing checkbox component
                    prop_checkbox = selection_meta.get("props_ui").get(prop)
                else:
                    # Initialize a new checkbox component
                    prop_checkbox = QCheckBox()
                    prop_checkbox.setChecked(True)
                    prop_checkbox.toggled.connect(self._update_table_layout)
                prop_checkbox.setVisible(True)
                self.sp_layout.addWidget(prop_checkbox, idx, 1)
                visible_props_ui[prop] = prop_checkbox

        # Update the selection meta
        self.state[self.selected_layer]["props_ui"] = visible_props_ui

    def _sort_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        self.state[self.selected_layer]["sort_by"] = self.sort_by_cb.currentText()
        self._update_table_layout()

    def _ascending_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        self.state[self.selected_layer]["ascending"] = self.sort_ascending.isChecked()
        self._update_table_layout()

    def _color_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return
        
        color_by = self.color_by_cb.currentText()
        self.state[self.selected_layer]["color_by"] = color_by
        
        selection_meta = self.state[self.selected_layer]
        df = selection_meta.get("df")
        if df is not None:
            _color_labels_layer_by_values(self.selected_layer, df, color_by)

    def _update_table_layout(self):
        selection_meta = self.state[self.selected_layer]
        _sync_table_ui_with_selection_meta(self.table, selection_meta)

    def _clicked_table(self):
        if self.selected_layer is None:
            return

        selection_meta = self.state[self.selected_layer]

        selection_context = SelectionContext(
            viewer=self.viewer,
            selected_layer=self.selected_layer,
            selected_table_idx=self.table.currentRow(),
            features_table=selection_meta.get("df"),
        )

        for func in self.table_click_callbacks:
            func(selection_context)
