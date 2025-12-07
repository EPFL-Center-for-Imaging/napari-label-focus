from napari_label_focus._context import SelectionContext
import napari.layers


def label_focus(ctx: SelectionContext) -> None:
    if ctx.features_table is None:
        return
    
    if not isinstance(ctx.selected_layer, napari.layers.Labels):
        return
    
    selected_table_label = ctx.features_table["label"].values[ctx.selected_table_idx]
    ctx.selected_layer.selected_label = selected_table_label
