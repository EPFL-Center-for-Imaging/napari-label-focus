import napari.layers
from qtpy.QtWidgets import QGridLayout, QWidget
from ._table import Table


class TableWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer
        self.selected_labels_layer = None

        self.setLayout(QGridLayout())
        self.table = Table(viewer=self.viewer)
        self.layout().addWidget(self.table, 0, 0)

        self.viewer.layers.selection.events.changed.connect(
            self._on_layer_selection_changed
        )

    def _on_layer_selection_changed(self, event):
        selected_layer = event.source.active
        if not isinstance(selected_layer, napari.layers.Labels):
            return

        if self.selected_labels_layer is not None:
            self.selected_labels_layer.events.paint.disconnect(
                lambda _: self.table.update_table_content(
                    self.selected_labels_layer
                )
            )
            self.selected_labels_layer.events.data.disconnect(
                lambda _: self.table.update_table_content(
                    self.selected_labels_layer
                )
            )
            if selected_layer.data.ndim == 4:
                self.viewer.dims.events.current_step.disconnect(
                    lambda e: self.table.handle_time_axis_changed(
                        e, self.selected_labels_layer
                    )
                )

        selected_layer.events.data.connect(
            lambda _: self.table.update_table_content(selected_layer)
        )
        selected_layer.events.paint.connect(
            lambda _: self.table.update_table_content(selected_layer)
        )
        if selected_layer.data.ndim == 4:
            self.viewer.dims.events.current_step.connect(
                lambda e: self.table.handle_time_axis_changed(
                    e, selected_layer
                )
            )

        self.selected_labels_layer = selected_layer
        self.table.update_table_content(selected_layer)
