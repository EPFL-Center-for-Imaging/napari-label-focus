from typing import Callable, Dict, List, Optional

import napari
import napari.layers
import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt
from qtpy.QtWidgets import QComboBox, QGridLayout, QLabel, QWidget

from napari_label_focus._featurizer import FeaturizerWidget
from napari_label_focus._utils import (color_labels_layer_by_values,
                                       sanitize_layer_features)

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


class ColorUIStore:
    def __init__(self) -> None:
        """This object is used to keep track of the selected display parameters, for each layer."""
        self.state: Dict[napari.layers.Layer, Dict] = {}

    def ensure_registered(self, layer: napari.layers.Layer) -> Dict:
        if layer in self.state:
            return self.state[layer]
        else:
            return self.register_new_layer(layer)

    def register_new_layer(self, layer: napari.layers.Layer) -> Dict:
        default_props = {
            "color_by": "",
            "alpha_by": "",
            "colormap": COLORMAPS[0],
        }
        self.state[layer] = default_props
        return default_props

    def get_color_by(self, layer: napari.layers.Layer) -> Optional[str]:
        props = self.ensure_registered(layer)
        return props.get("color_by")

    def set_color_by(self, layer: napari.layers.Layer, color_by: str):
        self.ensure_registered(layer)
        self.state[layer]["color_by"] = color_by
        
    def get_alpha_by(self, layer: napari.layers.Layer) -> Optional[str]:
        props = self.ensure_registered(layer)
        return props.get("alpha_by")
    
    def set_alpha_by(self, layer: napari.layers.Layer, alpha_by: str):
        self.ensure_registered(layer)
        self.state[layer]["alpha_by"] = alpha_by

    def get_colormap(self, layer: napari.layers.Layer) -> Optional[str]:
        props = self.ensure_registered(layer)
        return props.get("colormap")

    def set_colormap(self, layer: napari.layers.Layer, colormap: str):
        self.ensure_registered(layer)
        self.state[layer]["colormap"] = colormap

    def get_color_by_col_idx(self, layer: napari.layers.Layer) -> Optional[int]:
        features_df = sanitize_layer_features(layer)
        color_by = self.get_color_by(layer)
        if color_by in features_df.columns:
            for col_idx, col in enumerate(features_df.columns):
                if col == color_by:
                    return col_idx
    
    def get_alpha_by_col_idx(self, layer: napari.layers.Layer) -> Optional[int]:
        features_df = sanitize_layer_features(layer)
        alpha_by = self.get_alpha_by(layer)
        if alpha_by in features_df.columns:
            for col_idx, col in enumerate(features_df.columns):
                if col == alpha_by:
                    return col_idx

    def get_colormap_col_idx(self, layer: napari.layers.Layer) -> Optional[int]:
        colormap = self.get_colormap(layer)
        for col_idx, col in enumerate(COLORMAPS):
            if col == colormap:
                return col_idx


class FeaturesColorWidget(QWidget):
    def __init__(
        self,
        napari_viewer: napari.Viewer,
        featurizer_functs: Optional[List[Callable[[np.ndarray], pd.DataFrame]]] = None,
    ):
        """
        Configurable features color widget for Napari.

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
        self.props_ui_store = ColorUIStore()

        # Keep track of the selected layer
        self.selected_layer = None

        # Create the layout
        self.setLayout(QGridLayout())
        self.layout().setAlignment(Qt.AlignTop)

        # `Color by` = Hue of the selected labels layer
        self.layout().addWidget(QLabel("Color by", self), 0, 0)  # type: ignore
        self.color_by_cb = QComboBox()
        self.layout().addWidget(self.color_by_cb, 0, 1)  # type: ignore
        self.color_by_cb.currentTextChanged.connect(self._color_changed)

        # Colormap selection
        self.layout().addWidget(QLabel("Colormap", self), 1, 0)  # type: ignore
        self.colormap_cb = QComboBox()
        self.colormap_cb.addItems(COLORMAPS)
        self.layout().addWidget(self.colormap_cb, 1, 1)  # type: ignore
        self.colormap_cb.currentTextChanged.connect(self._colormap_changed)
        
        # Alpha (transparency)
        self.layout().addWidget(QLabel("Transparency", self), 2, 0)  # type: ignore
        self.alpha_by_cb = QComboBox()
        self.alpha_by_cb.addItems([""])
        self.layout().addWidget(self.alpha_by_cb, 2, 1)  # type: ignore
        self.alpha_by_cb.currentTextChanged.connect(self._alpha_changed)
        
        # Layer events
        self.viewer.layers.selection.events.changed.connect(
            self._layer_selection_changed
        )
        self.viewer.layers.events.inserted.connect(
            lambda e: self._layer_selection_changed(None)
        )
        self._layer_selection_changed(None)
        
    ### Callbacks that lead to updating the UI (layer selection change, features change, selected label change) ###

    def _layer_selection_changed(self, event):
        if event is None:
            layer = self.viewer.layers.selection.active
        else:
            layer = event.source.active

        if isinstance(self.selected_layer, napari.layers.Labels):
            self.selected_layer.events.features.disconnect(self._features_changed)

        if isinstance(layer, napari.layers.Labels):
            layer.events.features.connect(self._features_changed)

        self.selected_layer = layer

        self.update_ui(layer)

    def _features_changed(self, event):
        layer = event.sources[0]
        if not isinstance(layer, napari.layers.Labels):
            return
        self.update_ui(layer)

    ### UPDATE UI => Fills values for all display parameter comboboxes, etc. + redraws the UI ###

    def update_ui(self, layer: Optional[napari.layers.Layer]) -> None:
        if layer is None:
            return

        # Update color dropdown
        self._update_color_cb(layer)
        
        # Update alpha dropdown
        self._update_alpha_cb(layer)

        # Update colormap dropdown
        self._update_colormap_cb(layer)

    ### Events triggered by "update UI" ###

    def _update_color_cb(self, layer: napari.layers.Layer):
        col_idx = self.props_ui_store.get_color_by_col_idx(layer)

        self.color_by_cb.clear()

        df_features = sanitize_layer_features(layer)

        if len(df_features.columns) > 0:
            self.color_by_cb.addItems(df_features.columns)

        if col_idx is not None:
            self.color_by_cb.setCurrentIndex(col_idx)
    
    def _update_alpha_cb(self, layer: napari.layers.Layer):
        col_idx = self.props_ui_store.get_alpha_by_col_idx(layer)

        self.alpha_by_cb.clear()
        self.alpha_by_cb.addItems([""])

        df_features = sanitize_layer_features(layer)

        if len(df_features.columns) > 0:
            self.alpha_by_cb.addItems(df_features.columns)

        if col_idx is not None:
            self.alpha_by_cb.setCurrentIndex(col_idx)

    def _update_colormap_cb(self, layer: napari.layers.Layer):
        colormap_idx = self.props_ui_store.get_colormap_col_idx(layer)
        if colormap_idx is not None:
            self.colormap_cb.setCurrentIndex(colormap_idx)

    ### Callbacks that trigger a color change in the Labels layer ###

    def _color_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        color_by = self.color_by_cb.currentText()
        colormap = self.props_ui_store.get_colormap(self.selected_layer)
        alpha_by = self.props_ui_store.get_alpha_by(self.selected_layer)

        self.props_ui_store.set_color_by(self.selected_layer, color_by)

        color_labels_layer_by_values(
            self.selected_layer,
            self.selected_layer.features,
            color_by=color_by,
            alpha_by=alpha_by,
            colormap=colormap,
        )

    def _colormap_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        color_by = self.props_ui_store.get_color_by(self.selected_layer)
        colormap = self.colormap_cb.currentText()
        alpha_by = self.props_ui_store.get_alpha_by(self.selected_layer)
        
        self.props_ui_store.set_colormap(self.selected_layer, colormap)

        color_labels_layer_by_values(
            self.selected_layer,
            self.selected_layer.features,
            color_by=color_by,
            alpha_by=alpha_by,
            colormap=colormap,
        )

    def _alpha_changed(self):
        if not isinstance(self.selected_layer, napari.layers.Labels):
            return

        color_by = self.props_ui_store.get_color_by(self.selected_layer)
        colormap = self.props_ui_store.get_colormap(self.selected_layer)
        alpha_by = self.alpha_by_cb.currentText()

        self.props_ui_store.set_alpha_by(self.selected_layer, alpha_by)

        color_labels_layer_by_values(
            self.selected_layer,
            self.selected_layer.features,
            color_by=color_by,
            alpha_by=alpha_by,
            colormap=colormap,
        )
