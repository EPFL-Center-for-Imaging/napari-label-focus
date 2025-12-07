from typing import Callable, Dict, List, Optional

import napari
import napari.layers
import numpy as np
import pandas as pd
import skimage.measure
from napari.utils.notifications import show_warning
from napari_toolkit.containers.collapsible_groupbox import QCollapsibleGroupBox
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from napari_label_focus._context import SelectionContext
from napari_label_focus._event import label_focus


def _sync_table_with_context(table: QTableWidget, table_ctx: Dict, selected_label: Optional[int] = None) -> None:
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
            if (selected_label is not None) & (col == "label") & (int(float(val)) == selected_label):
                table.selectRow(k)


def _reset_table(table: QTableWidget) -> QTableWidget:
    table.clear()
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setColumnCount(1)
    table.setRowCount(1)
    table.setVisible(False)
    return table


def _create_labels_df(labels_layer: napari.layers.Labels):
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

    # TODO: This should call a configurable "featurize" method Callable[labels, DataFrame]
    df = pd.DataFrame(skimage.measure.regionprops_table(labels, properties=["label"]))

    # Merge existing features on the `label` column (TODO: improve this!)
    layer_features = labels_layer.features
    if ("label" in df.columns) and ("label" in layer_features.columns):
        df = pd.merge(df, layer_features, on="label")

    return df


class TableWidget(QWidget):
    def __init__(
        self,
        napari_viewer: napari.Viewer,
        trigger_fnct: Optional[List[Callable[[SelectionContext], None]]] = None,
    ):
        super().__init__()
        self.viewer = napari_viewer

        self.selected_layer: Optional[napari.layers.Layer] = None
        self.state = {}

        self.setLayout(QGridLayout())

        ### Triggered function ###
        self.trigger_fnct = [label_focus]  # Default behaviour
        if trigger_fnct is not None:
            for func in trigger_fnct:
                self.trigger_fnct.append(func)
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

        # Show properties
        self.show_props_gb = QCollapsibleGroupBox("Show properties")
        self.show_props_gb.setChecked(False)
        self.sp_layout = QGridLayout(self.show_props_gb)
        self.layout().addWidget(self.show_props_gb, 1, 0, 1, 4)

        # Table
        self.table = _reset_table(QTableWidget())
        self.table.clicked.connect(self._clicked_table)
        # TODO: Create an expansible layout for the table...
        self.layout().addWidget(self.table, 2, 0, 1, 4)

        # Layer events
        self.viewer.layers.selection.events.changed.connect(
            self._layer_selection_changed
        )
        self.viewer.layers.events.inserted.connect(
            lambda e: self._layer_selection_changed(None)
        )
        self._layer_selection_changed(None)

    def _new_layer_selected(self, selected_layer):
        self.state[self.selected_layer] = {
            "props_ui": {},
            "sort_by": None,
            "ascending": self.sort_ascending.isChecked(),
            "df": None,
        }

        if isinstance(self.selected_layer, napari.layers.Labels):
            self.selected_layer.events.paint.disconnect(self._update_labels_df)
            self.selected_layer.events.data.disconnect(self._update_labels_df)
            self.selected_layer.events.features.disconnect(self._update_labels_df)
            self.selected_layer.events.selected_label.disconnect(self._selected_label_changed)

        if isinstance(selected_layer, napari.layers.Labels):
            selected_layer.events.data.connect(self._update_labels_df)
            selected_layer.events.paint.connect(self._update_labels_df)
            selected_layer.events.features.connect(self._update_labels_df)
            selected_layer.events.selected_label.connect(self._selected_label_changed)

    def _selected_label_changed(self, event):
        layer = event.sources[0]
        if isinstance(layer, napari.layers.Labels):
            lpui = self.state[self.selected_layer]
            _sync_table_with_context(self.table, lpui, selected_label=layer.selected_label)
        
    def _layer_selection_changed(self, event):
        if event is None:
            selected_layer = self.viewer.layers.selection.active
        else:
            selected_layer = event.source.active

        self.selected_layer = selected_layer

        if not self.selected_layer in self.state:
            self._new_layer_selected(selected_layer)

        self._update_labels_df()

    def _update_labels_df(self):
        if isinstance(self.selected_layer, napari.layers.Labels):
            self.state[self.selected_layer]["df"] = _create_labels_df(
                self.selected_layer
            )
        self.update_ui()

    def update_ui(self) -> None:
        lpui = self.state[self.selected_layer]

        # Update sort dropdown
        self._update_sort_cb(lpui)

        # Update ascending state
        self._update_ascending(lpui)

        # Update visible properties
        self._update_visible_props(lpui)

        # Sort and update the table
        self._update_table()

    def _update_ascending(self, lpui):
        self.sort_ascending.setChecked(lpui["ascending"])

    def _update_sort_cb(self, lpui):
        self.sort_by_cb.clear()
        if lpui.get("df") is not None:

            # items = []  # TODO: THIS DOESNT WORK
            # for k, v in lpui["props_ui"]:
            #     if v.isChecked():
            #         items.append(k)
            # self.sort_by_cb.addItems(items)

            self.sort_by_cb.addItems(lpui["df"].columns)
        if lpui.get("sort_by") is not None:
            for i, c in enumerate(lpui["df"].columns):
                if c == lpui["sort_by"]:
                    self.sort_by_cb.setCurrentIndex(i)

    def _update_visible_props(self, lpui):
        for i in reversed(range(self.sp_layout.count())):
            ui_item = self.sp_layout.itemAt(i)
            if ui_item is not None:
                ui_item_widget = ui_item.widget()
                if ui_item_widget is not None:
                    ui_item_widget.setParent(None)

        props_ui = {}
        if lpui.get("df") is not None:
            for idx, prop in enumerate(lpui["df"].columns):
                self.sp_layout.addWidget(QLabel(prop, self), idx, 0)
                if lpui.get("props_ui").get(prop) is not None:
                    prop_checkbox = lpui.get("props_ui").get(prop)
                else:
                    prop_checkbox = QCheckBox()
                    prop_checkbox.setChecked(True)
                    prop_checkbox.toggled.connect(self._update_table)
                prop_checkbox.setVisible(True)
                self.sp_layout.addWidget(prop_checkbox, idx, 1)
                props_ui[prop] = prop_checkbox

        self.state[self.selected_layer]["props_ui"] = props_ui

    def _sort_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        self.state[self.selected_layer]["sort_by"] = self.sort_by_cb.currentText()
        self._update_table()

    def _ascending_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        self.state[self.selected_layer]["ascending"] = self.sort_ascending.isChecked()
        self._update_table()

    def _update_table(self):
        lpui = self.state[self.selected_layer]
        _sync_table_with_context(self.table, lpui)

    def _clicked_table(self):
        if self.selected_layer is None:
            return

        lpui = self.state[self.selected_layer]

        selection_context = SelectionContext(
            viewer=self.viewer,
            selected_layer=self.selected_layer,
            selected_table_idx=self.table.currentRow(),
            features_table=lpui.get("df"),
        )

        for func in self.trigger_fnct:
            func(selection_context)
