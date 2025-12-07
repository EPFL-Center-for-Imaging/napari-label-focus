from napari_label_focus._context import SelectionContext
import napari.layers


def default_table_click_event(ctx: SelectionContext) -> None:
    """Default table click event. Selects the label from the selected table row in the labels layer."""
    if ctx.features_table is None:
        return

    if not isinstance(ctx.selected_layer, napari.layers.Labels):
        return

    selected_table_label = ctx.features_table["label"].values[ctx.selected_table_idx]
    ctx.selected_layer.selected_label = selected_table_label
