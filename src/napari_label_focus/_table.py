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

    def _clicked_table(self):
        row = self._view.currentRow()
        if self._layer is None:
            return

        self._layer.selected_label = self._table["label"][row]

        z0 = int(self._table["bbox-0"][row])
        z1 = int(self._table["bbox-3"][row])
        x0 = int(self._table["bbox-1"][row])
        x1 = int(self._table["bbox-4"][row])
        y0 = int(self._table["bbox-2"][row])
        y1 = int(self._table["bbox-5"][row])

        cx = (x1 + x0) / 2
        cy = (y1 + y0) / 2
        cz = int((z1 + z0) / 2)
        self._viewer.camera.center = (0.0, cx, cy)
        self._viewer.camera.angles = (0.0, 0.0, 90.0)

        label_size = max(x1 - x0, y1 - y0)
        self._viewer.camera.zoom = max(20 - 0.2 * label_size, 5)

        current_step = self._viewer.dims.current_step
        current_step = np.array(current_step)
        current_step[0] = cz
        current_step = tuple(current_step)
        self._viewer.dims.current_step = current_step

    def _save_csv(self):
        if self._layer is None:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save as CSV", ".", "*.csv"
        )

        pd.DataFrame(self._table).to_csv(filename)

    def update_content(self, layer: napari.layers.Labels):
        self._layer = layer
        if self._layer is None:
            self._view.clear()
            self._view.setRowCount(1)
            self._view.setHorizontalHeaderItem(0, QTableWidgetItem('label'))
            self._view.setHorizontalHeaderItem(1, QTableWidgetItem('volume'))
            return

        labels = self._layer.data
        if labels.sum() == 0:
            return
        
        if len(labels.shape) == 2:
            labels = labels[None]  # Add an extra dimension
        
        properties = skimage.measure.regionprops_table(labels, properties=["label", "area", "bbox"])
        df = pd.DataFrame.from_dict(properties)
        df.rename(columns={"area": "volume"}, inplace=True)
        df.sort_values(by="volume", ascending=False, inplace=True)
        self.set_content(df)

    def set_content(self, df: pd.DataFrame):
        self._table = df
        self._view.clear()
        self._view.setRowCount(len(self._table))
        self._view.setHorizontalHeaderItem(0, QTableWidgetItem('label'))
        self._view.setHorizontalHeaderItem(1, QTableWidgetItem('volume'))

        for i, (lab, vol) in self._table[['label', 'volume']].iterrows():
            self._view.setItem(i, 0, QTableWidgetItem(str(lab)))
            self._view.setItem(i, 1, QTableWidgetItem(str(vol)))
