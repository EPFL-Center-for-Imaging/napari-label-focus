# from qtpy.QtWidgets import QWidget, QComboBox, QDialog, QGridLayout, QLabel
# import napari.layers

# class LayerChangeWidget(QDialog):
#     def __init__(self, viewer):
#         super().__init__()
#         self.viewer = viewer

#         widget = QWidget(self)
#         layout = QGridLayout(widget)
#         layout.addWidget(QLabel("Labels layers", self), 0, 0)
#         self.cb = QComboBox()
#         layout.addWidget(self.cb, 0, 1)
#         self.viewer.events.layers_change.connect(self._on_layer_change)
#         self.cb.currentTextChanged.connect(self._on_cb_change)
#         self._on_layer_change(None)

#     def _on_layer_change(self, e):
#         self.cb.clear()
#         for x in self.viewer.layers:
#             if isinstance(x, napari.layers.Labels):
#                 self.cb.addItem(x.name, x.data)

#         if self.cb.count() < 1:  # Nothing in the combobox
#             print('Nothing in the combobox')
#         else:
#             print('Objects in the combobox: ', self.cb.count())

#     def _on_cb_change(self, selection):
#         print(selection)
