from typing import Callable, List, Optional

import napari.layers
import numpy as np
import pandas as pd
import skimage.measure
from napari.utils.notifications import show_warning

from napari_label_focus._utils import sanitize_layer_features


def default_featurizer(labels: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(skimage.measure.regionprops_table(labels, properties=["label"]))


class Featurizer:
    def __init__(
        self,
        featurizer_functs: Optional[List[Callable[[np.ndarray], pd.DataFrame]]] = None,
    ) -> None:
        self.featurizer_functs: List = [default_featurizer]
        if isinstance(featurizer_functs, List):
            self.featurizer_functs.extend(featurizer_functs)

    def recompute_features(
        self, labels_layer: napari.layers.Layer
    ) -> Optional[pd.DataFrame]:
        """
        Performs checks to sanitize a labels layer and its data, then runs featurizer functions and updates layer features.
        """
        if not isinstance(labels_layer, napari.layers.Labels):
            return

        # Sanitize labels layer data
        labels = labels_layer.data

        if not isinstance(labels, np.ndarray):
            show_warning("Labels data should be a Numpy array")
            return

        # Sanitize labels layer features
        features_df = sanitize_layer_features(labels_layer)

        # Compute the "default featurizer"
        merged_df = default_featurizer(labels)

        # Merge it with existing features
        if "label" in features_df.columns:
            merged_df = self._merge_incoming_df(features_df, merged_df)

        # Compute extra feature dataframes and merge them into the layer features
        for featurizer_func in self.featurizer_functs:
            df_incoming = featurizer_func(labels)

            if "label" not in df_incoming.columns:
                show_warning(
                    "Featurizer should output a dataframe with a 'label' column"
                )
                continue

            merged_df = self._merge_incoming_df(df_incoming, merged_df)

        # Update the layer features
        labels_layer.features = merged_df

    def _merge_incoming_df(
        self, df_incoming: pd.DataFrame, df_existing: pd.DataFrame
    ) -> pd.DataFrame:
        # Shared columns that are not "label"
        shared_cols = df_incoming.columns.intersection(df_existing.columns).difference(
            ["label"]
        )

        # Left merge to keep only label rows present in the incoming features
        df_merged = df_incoming.merge(
            df_existing, on="label", how="left", suffixes=("_incoming", "_existing")
        )

        # Overwrite existing values with incoming values
        for col in shared_cols:
            df_merged[col] = df_merged[f"{col}_incoming"]

        # Drop all suffixed columns
        cols_to_drop = [f"{col}_incoming" for col in shared_cols] + [
            f"{col}_existing" for col in shared_cols
        ]
        df_merged = df_merged.drop(columns=cols_to_drop)

        return df_merged


class FeaturizerWidget:
    def __init__(
        self,
        napari_viewer: napari.Viewer,
        featurizer_functs: Optional[List[Callable[[np.ndarray], pd.DataFrame]]] = None,
    ):
        self.viewer = napari_viewer

        self.featurizer_functs = Featurizer(featurizer_functs=featurizer_functs)

        # Keep track of the selected layer
        self.selected_layer = None
        
        # Keep track of layers selected at least once to avoid recomputing their features on layer change
        self.seen_layers = []

        # Layer events
        self.viewer.layers.selection.events.changed.connect(self._selection_changed)
        self.viewer.layers.events.inserted.connect(
            lambda e: self._selection_changed(None)
        )
        self._selection_changed(None)

    def _selection_changed(self, event=None):
        if event is None:
            layer = self.viewer.layers.selection.active
        else:
            layer = event.source.active

        if not isinstance(layer, napari.layers.Layer):
            return

        # Connect the "paint" and "data change" events to recomputing features
        if isinstance(self.selected_layer, napari.layers.Labels):
            self.selected_layer.events.paint.disconnect(self._recompute)
            self.selected_layer.events.data.disconnect(self._recompute)

        if isinstance(layer, napari.layers.Labels):
            layer.events.data.connect(self._recompute)
            layer.events.paint.connect(self._recompute)

        self.selected_layer = layer

        # Only compute features on selection change when the layer is seen for the first time
        if layer not in self.seen_layers:
            self.featurizer_functs.recompute_features(layer)

    def _recompute(self, event):
        layer = event.sources[0]

        self.featurizer_functs.recompute_features(layer)
