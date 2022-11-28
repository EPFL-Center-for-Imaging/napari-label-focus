import numpy as np

from napari_label_focus import TableGeneratorWidget


def test_example_q_widget(make_napari_viewer, capsys):
    # make viewer and add an image layer using our fixture
    viewer = make_napari_viewer()
    test_labels = np.arange(0, 9).reshape((3, 3))
    viewer.add_labels(test_labels)

    # create our widget, passing in the viewer
    my_widget = TableGeneratorWidget(viewer)

    assert len(my_widget.table._table) == len(np.unique(test_labels)) - 1

