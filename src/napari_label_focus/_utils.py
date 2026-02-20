from collections import defaultdict
from typing import Optional
import napari.layers
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from skimage.color import hsv2rgb
from napari.utils import DirectLabelColormap
from napari.utils.notifications import show_warning


def sanitize_layer_features(layer: napari.layers.Layer) -> pd.DataFrame:
    """Converts existing layer features to a Pandas DataFrame (empty if features are non-existent, or incompatible with the plugin)."""
    if not hasattr(layer, "features"):
        return pd.DataFrame()
    else:
        features = getattr(layer, "features")
        if isinstance(features, pd.DataFrame):
            return features
        else:
            show_warning(
                f"Layer `{layer.name}` contains features that aren't a pandas DataFrame (not displayable in the features table widget)."
            )
            return pd.DataFrame()


def color_labels_layer_by_values(
    layer: napari.layers.Labels,
    features_df: pd.DataFrame,
    color_by: Optional[str],
    alpha_by: Optional[str],
    colormap: Optional[str],
):
    """Colorize a napari Labels layer based on the values of a column in a features dataframe."""
    # Sanitize color variables
    if (color_by is None) or (color_by == ""):
        return
    
    if (colormap is None) or (colormap == ""):
        return
    
    # Drop the NaNs
    features_df_filtered = features_df.dropna(axis=0)
    if len(features_df_filtered) == 0:
        return

    # Check that the `label` column is present
    if "label" not in features_df_filtered.columns:
        raise ValueError("Features dataframe does not have a `label` column.")
    label_values = features_df_filtered["label"].values

    # Check the values to plot from the dataframe
    numeric_cols = features_df_filtered.select_dtypes(include=[np.number]).columns
    if color_by not in numeric_cols:
        raise ValueError(
            f"Column {color_by} is either not present or non-numeric (cannot be plotted)."
        )

    plot_vals = features_df_filtered[color_by].values
    if not isinstance(plot_vals, np.ndarray):
        raise ValueError(
            f"Values in column {color_by} are not a NumPy array (cannot be plotted)"
        )
    
    # Alpha values
    if alpha_by == "":
        relative_alpha_vals = np.ones_like(plot_vals)  # Default to full opacity
    else:
        alpha_vals = features_df_filtered[alpha_by].values
        if not isinstance(alpha_vals, np.ndarray):
            print(f"Values in column {alpha_by} are not a NumPy array (cannot be plotted)")
            relative_alpha_vals = np.ones_like(plot_vals)  # Default to full opacity
        else:
            min_vals = np.min(alpha_vals)
            max_vals = np.max(alpha_vals)
            val_range = max_vals - min_vals
            if val_range > 0:
                relative_alpha_vals = (alpha_vals - min_vals) / val_range
            else:
                relative_alpha_vals = (alpha_vals - min_vals) + 1
    
    if colormap == "random":
        # Special case for random (not a matplotlib colormap)
        unique_plot_vals = np.unique(plot_vals)
        hue = np.random.random(len(unique_plot_vals))
        hue_map = {val: h for val, h in zip(unique_plot_vals, hue)}
        hues = [hue_map[h] for h in plot_vals]
        saturation = np.ones(len(plot_vals))
        value = np.ones(len(plot_vals))
        hsv_random = np.stack((hues, saturation, value)).T
        rgb_random = hsv2rgb(hsv_random)
        rgba = np.hstack((rgb_random, relative_alpha_vals[None].T))
    else:
        # Rescale values to [0-1] for colormapping
        min_vals = np.min(plot_vals)
        max_vals = np.max(plot_vals)
        val_range = max_vals - min_vals
        if val_range > 0:
            relative_vals = (plot_vals - min_vals) / val_range
        else:
            relative_vals = (plot_vals - min_vals) + 1
        cmap = plt.get_cmap(colormap)
        rgba = cmap(relative_vals)
        rgba[:, 3] = relative_alpha_vals

    color_dict = defaultdict(lambda: np.zeros(4))
    for lab, color in zip(label_values, rgba):
        if lab == 0:
            color[-1] = 0 # Background transparent
        color_dict[lab] = color

    layer.events.selected_label.block()
    layer.colormap = DirectLabelColormap(color_dict=color_dict)
    layer.events.selected_label.unblock()
    layer.refresh()
