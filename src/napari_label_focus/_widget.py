"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/stable/plugins/guides.html?#widgets

Replace code below according to your needs.
"""
from typing import TYPE_CHECKING

from magicgui import magic_factory
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QWidget
from qtpy.QtWidgets import QWidget, QComboBox, QDialog, QGridLayout, QLabel

import napari.layers

if TYPE_CHECKING:
    import napari


class TableGeneratorWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        # btn = QPushButton("Click me Table")
        # btn.clicked.connect(self._on_click)
        # self.setLayout(QHBoxLayout())
        # self.layout().addWidget(btn)

        self.setLayout(QGridLayout())
        # layout = QGridLayout(widget)
        self.layout().addWidget(QLabel("Labels layers", self), 0, 0)
        self.cb = QComboBox()
        self.layout().addWidget(self.cb, 0, 1)
        self.viewer.events.layers_change.connect(self._on_layer_change)
        self.cb.currentTextChanged.connect(self._on_cb_change)
        self._on_layer_change(None)

    # def _on_click(self):
    #     print("napari has", len(self.viewer.layers), "layers")

    def _on_layer_change(self, e):
        self.cb.clear()
        for x in self.viewer.layers:
            if isinstance(x, napari.layers.Labels):
                self.cb.addItem(x.name, x.data)

        if self.cb.count() < 1:  # Nothing in the combobox
            print('Nothing in the combobox')
        else:
            print('Objects in the combobox: ', self.cb.count())

    def _on_cb_change(self, selection):
        print(selection)


# class ExampleQWidget(QWidget):
#     # your QWidget.__init__ can optionally request the napari viewer instance
#     # in one of two ways:
#     # 1. use a parameter called `napari_viewer`, as done here
#     # 2. use a type annotation of 'napari.viewer.Viewer' for any parameter
#     def __init__(self, napari_viewer):
#         super().__init__()
#         self.viewer = napari_viewer

#         btn = QPushButton("Click me modified!")
#         btn.clicked.connect(self._on_click)

#         self.setLayout(QHBoxLayout())
#         self.layout().addWidget(btn)

#     def _on_click(self):
#         print("napari has", len(self.viewer.layers), "layers")

# @magic_factory
# def example_magic_widget(img_layer: "napari.layers.Image"):
#     print(f"you have selected {img_layer}")

# # Uses the `autogenerate: true` flag in the plugin manifest
# # to indicate it should be wrapped as a magicgui to autogenerate
# # a widget.
# def example_function_widget(img_layer: "napari.layers.Image"):
#     print(f"you have selected {img_layer}")
