![EPFL Center for Imaging logo](https://imaging.epfl.ch/resources/logo-for-gitlab.svg)
# Configurable Features Table for Napari

[demo.webm](https://github.com/user-attachments/assets/d44aa86c-7976-4240-91bd-ca194762d038)

This plugin is similar to Napari's built-in [features table widget](https://napari.org/0.6.3/gallery/features_table_widget.html), but optimized for usage with **2D and 3D `Labels` layers**. It offers extra options to:

- Sort table values.
- Hide or show table columns.
- Colorize `Labels` based on feature values, with different color maps.
- Connect your own callback functions to customize what happens when users click on a table row.
- Connect your own featurizer functions that run automatically when the data in the `Labels` changes and update the displayed table.

The content of the table is a graphical view of the `features` attribute of a `Labels` layer.

## Displaying the table

Open the table from `Plugins > Features Table` in Napari.

The table displays features from the **currently selected layer** in the layers list. It will automatically update when the layer selection changes. If multiple layers are selected, only features from the first selected layer will be displayed.

## Connecting featurizer functions

By default, the table displays a `label` column for the selected `Labels` layer, along with any pre-existing features that can be matched with the `label` column (they should be in Pandas DataFrame format with at least a 'label' column).

You can customize the behaviour of the plugin to **update features automatically** when a new Labels layer is selected, or when its data changes, based on a featurizer function that you provide. Featurizer functions will receive as input the labels layer data as a Numpy array, and should return a Pandas DataFrame with at least a `label` column, along with any other feature columns.

For example, the following code extends the behaviour of the table to display the `area` (or volume) of objects:

```python
import napari
import pandas as pd
from skimage.measure import regionprops_table
from napari_label_focus import ConfigurableFeaturesTableWidget

# Write an "area" featurizer
def area_featurizer(labels: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(regionprops_table(labels, properties=["label", "area"]))

if __name__ == "__main__":
    viewer = napari.Viewer()
    widget = ConfigurableFeaturesTableWidget(viewer, featurizer_functs=[area_featurizer])
    viewer.window.add_dock_widget(widget)
    napari.run()
```

If more than one featurizer function is provided, these functions will be run one by one and the results will be merged into a single features DataFrame.

## Controlling what clicking on a table row does

By default, clicking on a table row selects the corresponding label in the `Labels` layer. This behaviour can be extended by adding callback functions to the *table_click_callbacks* parameter of the table widget. The callback functions receive a selection context object with references to the viewer, selected layer, selected table row, and the table itself.

For example:

```python
import napari
from napari_label_focus import ConfigurableFeaturesTableWidget, SelectionContext

def print_selection_context(ctx: SelectionContext):
    print(f"Napari viewer: {ctx.viewer}")
    print(f"Selected layer: {ctx.selected_layer}")
    print(f"Selected table row: {ctx.selected_table_idx}")
    print(f"Features table: {ctx.features_table}")

if __name__ == "__main__":
    viewer = napari.Viewer()
    widget = ConfigurableFeaturesTableWidget(viewer, table_click_callbacks=[print_selection_context])
    viewer.window.add_dock_widget(widget)
    napari.run()
```

In this case, the function `print_selection_context` gets called whenever users click on a table row.

## Installation

You can install `napari-label-focus` via [pip]:

    pip install napari-label-focus

## Contributing

Contributions are very welcome.

## License

This software is distributed under the terms of the [BSD-3](http://opensource.org/licenses/BSD-3-Clause) license.

## Issues

If you encounter any problems, please file an issue along with a detailed description.
