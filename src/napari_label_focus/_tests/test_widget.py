import numpy as np

from napari_label_focus import TableWidget


def test_example_q_widget(make_napari_viewer, capsys):
    viewer = make_napari_viewer()
    test_labels = np.arange(0, 9).reshape((3, 3))
    viewer.add_labels(test_labels)

    my_widget = TableWidget(viewer)

    assert len(my_widget.table._table) == len(np.unique(test_labels)) - 1

