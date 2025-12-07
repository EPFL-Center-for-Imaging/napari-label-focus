import numpy as np
import pandas as pd
import skimage.measure


def default_featurizer(labels: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(skimage.measure.regionprops_table(labels, properties=["label"]))
