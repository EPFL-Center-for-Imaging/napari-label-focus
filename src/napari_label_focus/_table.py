import napari
from pandas import DataFrame
from qtpy.QtWidgets import QTableWidget, QHBoxLayout, QTableWidgetItem, QWidget, QGridLayout, QPushButton
import pandas as pd
from typing import Union
import numpy as np
import skimage.measure


class TableWidget(QWidget):
    """
    The table widget represents a table inside napari.
    Tables are just views on `properties` of `layers`.
    """
    def __init__(self, layer: napari.layers.Layer = None, viewer:napari.Viewer = None):
        super().__init__()

        self._layer = layer
        self._viewer = viewer

        self._view = QTableWidget()
        self._view.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        self.set_content({})

        self._view.clicked.connect(self._clicked_table)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_clicked)

        self.setLayout(QGridLayout())

        action_widget = QWidget()
        action_widget.setLayout(QHBoxLayout())
        action_widget.layout().addWidget(refresh_btn)
        self.layout().addWidget(action_widget)
        self.layout().addWidget(self._view)
        action_widget.layout().setSpacing(3)
        action_widget.layout().setContentsMargins(0, 0, 0, 0)

    def _clicked_table(self):
        if "label" in self._table.keys():
            row = self._view.currentRow()
            label = self._table["label"][row]
            self._layer.selected_label = label

            # Focus the viewr on selected label
            z0 = int(self._table['bbox-0'][row])
            z1 = int(self._table['bbox-3'][row])
            x0 = int(self._table['bbox-1'][row])
            x1 = int(self._table['bbox-4'][row])
            y0 = int(self._table['bbox-2'][row])
            y1 = int(self._table['bbox-5'][row])

            cx = (x1 + x0) / 2
            cy = (y1 + y0) / 2
            cz = int((z1 + z0) / 2)
            self._viewer.camera.center = (0.0, cx, cy)
            self._viewer.camera.angles = (0.0, 0.0, 90.0)

            current_step = self._viewer.dims.current_step
            current_step = np.array(current_step)
            current_step[0] = cz
            current_step = tuple(current_step)
            self._viewer.dims.current_step = current_step

    def _refresh_clicked(self): self.update_content(self._layer)

    def set_content(self, table : dict):
        """
        Overwrites the content of the table with the content of a given dictionary.
        """
        if table is None:
            table = {}

        self._table = table

        self._view.clear()
        try:
            self._view.setRowCount(len(next(iter(table.values()))))
            self._view.setColumnCount(2)
        except StopIteration:
            pass
        
        for i, column in enumerate(table.keys()):
            if column not in ['label', 'area']:
                continue
            self._view.setHorizontalHeaderItem(i, QTableWidgetItem(column))
            for j, value in enumerate(table.get(column)):
                self._view.setItem(j, i, QTableWidgetItem(str(value)))

    def get_content(self) -> dict:
        """
        Returns the current content of the table
        """
        return self._table

    def update_content(self, layer: napari.layers.Labels):
        """
        Read the content of the table from the associated labels_layer and overwrites the current content.
        """
        self._layer = layer
        self._regionprops_table()
        self.set_content(self._layer.properties)

    def append_content(self, table: Union[dict, DataFrame], how: str = 'outer'):
        """
        Append data to table.

        Parameters
        ----------
        table : Union[dict, DataFrame]
            New data to be appended.
        how : str, OPTIONAL
            Method how to join the data. See also https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.merge.html
        Returns
        -------
        None.
        """
        # Check input type
        if not isinstance(table, DataFrame):
            table = DataFrame(table)

        _table = DataFrame(self._table)

        # Check whether there are common columns and switch merge type accordingly
        common_columns = np.intersect1d(table.columns, _table.columns)
        if len(common_columns) == 0:
            table = pd.concat([table, _table])
        else:
            table = pd.merge(table, _table, how=how, copy=False)

        self.set_content(table.to_dict('list'))


    def _regionprops_table(self):
        """
        Adds a table widget to a given napari viewer with quantitative analysis results derived from an image-label pair.
        """
        labels = self._layer.data

        table = skimage.measure.regionprops_table(
            np.asarray(labels).astype(int), 
            properties=['label', 'area', 'centroid', 'bbox'], 
        )

        self._layer.properties = table
