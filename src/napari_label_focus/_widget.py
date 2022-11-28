"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/stable/plugins/guides.html?#widgets

Replace code below according to your needs.
"""
from typing import TYPE_CHECKING

from qtpy.QtWidgets import QHBoxLayout, QPushButton, QWidget
from qtpy.QtWidgets import QWidget, QComboBox, QDialog, QGridLayout, QLabel

import napari.layers

from ._table import TableWidget

if TYPE_CHECKING:
    import napari


class TableGeneratorWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        import numpy as np
        import tifffile
        labs = tifffile.imread('/home/wittwer/code/napari-focus/napari-label-focus/src/napari_label_focus/test_labels.tif')
        labs = np.swapaxes(labs, 0, 2)
        self.viewer.add_image(np.zeros_like(labs), colormap='viridis')
        self.viewer.add_labels(labs)

        self.setLayout(QGridLayout())
        self.cb = QComboBox()
        self.layout().addWidget(self.cb, 0, 0)
        self.table = TableWidget(viewer=self.viewer)
        self.layout().addWidget(self.table, 1, 0)

        self.viewer.events.layers_change.connect(self._on_layer_change)
        self.cb.currentTextChanged.connect(self._on_cb_change)
        self._on_layer_change(None)


    def _on_layer_change(self, e):
        self.cb.clear()
        for x in self.viewer.layers:
            if isinstance(x, napari.layers.Labels):
                self.cb.addItem(x.name, x.data)

    def _on_cb_change(self, selection: str):
        selected_layer = None
        for l in self.viewer.layers:
            if l.name == selection:
                selected_layer = l
                break
        
        if selected_layer is None:
            return
        
        self.table.update_content(selected_layer)

