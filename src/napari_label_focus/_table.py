import napari
import numpy as np
import pandas as pd
import skimage.measure
from qtpy.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

class Table(QWidget):
    def __init__(self, layer: napari.layers.Layer = None, viewer: napari.Viewer = None):
        super().__init__()
        self._layer = layer
        self._viewer = viewer
        self._view = QTableWidget()
        self._view.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._view.setColumnCount(2)
        self._view.setRowCount(1)
        self._view.setColumnWidth(0, 30)
        self._view.setColumnWidth(1, 120)
        self._view.setHorizontalHeaderItem(0, QTableWidgetItem('label'))
        self._view.setHorizontalHeaderItem(1, QTableWidgetItem('volume'))
        self._view.clicked.connect(self._clicked_table)

        save_button = QPushButton("Save as CSV")
        save_button.clicked.connect(lambda _: self._save_csv())

        self.setLayout(QGridLayout())
        action_widget = QWidget()
        action_widget.setLayout(QHBoxLayout())
        action_widget.layout().addWidget(save_button)
        self.layout().addWidget(action_widget)
        self.layout().addWidget(self._view)
        action_widget.layout().setSpacing(3)
        action_widget.layout().setContentsMargins(0, 0, 0, 0)

        self.df = None
        self.current_time = None

    @property
    def axes(self):
        if self._viewer.dims.ndisplay == 3:
            return
        
        # 2D case
        axes = list(self._viewer.dims.displayed)

        # 3D case
        if self._layer.data.ndim == 3:
            axes.insert(0, list(set([0, 1, 2]) - set(list(self._viewer.dims.displayed)))[0])

        # 4D case (not used yet)
        elif self._layer.data.ndim == 4:
            xxx = set(self._viewer.dims.displayed)
            to_add = list(set([0, 1, 2, 3]) - xxx)
            axes = to_add + axes
        
        return axes

    def _clicked_table(self):
        row = self._view.currentRow()
        if self._layer is None:
            return

        self._layer.selected_label = self.df["label"].values[row]

        x0 = int(self.df["bbox-0"].values[row])
        x1 = int(self.df["bbox-3"].values[row])
        y0 = int(self.df["bbox-1"].values[row])
        y1 = int(self.df["bbox-4"].values[row])
        z0 = int(self.df["bbox-2"].values[row])
        z1 = int(self.df["bbox-5"].values[row])

        label_size = max(x1 - x0, y1 - y0, z1 - z0)

        centers = np.array([(x1 + x0) / 2, (y1 + y0) / 2, (z1 + z0) / 2])

        # Note - there is probably something easier to set up with viewer.camera.calculate_nd_view_direction()
        if self._viewer.dims.ndisplay == 3:
            self._viewer.camera.center = (0.0, centers[1], centers[2])
            self._viewer.camera.angles = (0.0, 0.0, 90.0)
        else:
            current_center = np.array(self._viewer.camera.center)

            if len(self.axes) == 2:
                current_center[1] = centers[1:][self.axes][0]
                current_center[2] = centers[1:][self.axes][1]                
            elif len(self.axes) == 3:
                current_center[1] = centers[self.axes[1]]
                current_center[2] = centers[self.axes[2]]
                # In 3D, also adjust the current step
                current_step = np.array(self._viewer.dims.current_step)[self.axes]
                current_step[self.axes[0]] = int(centers[self.axes[0]])
                self._viewer.dims.current_step = tuple(current_step)

            elif len(self.axes) == 4:
                print("4D case not implemented yet.")

            self._viewer.camera.center = tuple(current_center)

        self._viewer.camera.zoom = max(3 - label_size * 0.005, 1.0)

    def _save_csv(self):
        if self._layer is None:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save as CSV", ".", "*.csv"
        )

        pd.DataFrame(self.df).to_csv(filename)

    def updated_content_2D_or_3D(self, labels):
        """Compute volumes and update the table UI in the 2D and 3D cases."""
        properties = skimage.measure.regionprops_table(labels, properties=["label", "area", "bbox"])
        self.df = pd.DataFrame.from_dict(properties)
        self.df.rename(columns={"area": "volume"}, inplace=True)
        self.df.sort_values(by="volume", ascending=False, inplace=True)

        # Regenerate the table UI
        self._view.clear()
        self._view.setRowCount(len(self.df))
        self._view.setHorizontalHeaderItem(0, QTableWidgetItem('label'))
        self._view.setHorizontalHeaderItem(1, QTableWidgetItem('volume'))

        k = 0
        for _, (lab, vol) in self.df[['label', 'volume']].iterrows():
            self._view.setItem(k, 0, QTableWidgetItem(str(lab)))
            self._view.setItem(k, 1, QTableWidgetItem(str(vol)))
            k += 1

    def handle_time_axis_changed(self, event, source_layer):
        current_time = event.value[0]
        if (current_time != self.current_time) | (self.current_time is None):
            # This gets called multiple times when moving forward in time. Why?
            self.current_time = current_time
            self.update_content(source_layer)

    def update_content(self, layer: napari.layers.Labels):
        self._layer = layer
        if self._layer is None:
            self._view.clear()
            self._view.setRowCount(1)
            self._view.setColumnWidth(0, 30)
            self._view.setColumnWidth(1, 120)
            self._view.setHorizontalHeaderItem(0, QTableWidgetItem('label'))
            self._view.setHorizontalHeaderItem(1, QTableWidgetItem('volume'))
            return

        labels = self._layer.data#.copy()

        if len(labels.shape) == 2:
            labels = labels[None]  # Add an extra dimension in the 2D case
        
        elif len(labels.shape) == 4:
            labels = labels[self._viewer.dims.current_step[0]]

        if labels.sum() == 0:
            return

        self.updated_content_2D_or_3D(labels)