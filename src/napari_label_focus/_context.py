from dataclasses import dataclass
import napari
import napari.layers
import pandas as pd


@dataclass
class SelectionContext:
    """Selection context passed to table click events."""
    viewer: napari.Viewer
    selected_layer: napari.layers.Layer
    selected_table_idx: int
    features_table: pd.DataFrame
