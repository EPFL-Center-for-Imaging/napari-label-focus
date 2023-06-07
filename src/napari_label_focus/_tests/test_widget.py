import numpy as np

from napari_label_focus import TableWidget
from skimage.morphology import label
from skimage.draw import disk

def test_example_q_widget(make_napari_viewer, capsys):
    viewer = make_napari_viewer()

    test_labels = np.zeros((1000, 1800))
    i = 0
    for r in range(10, 200, 20):
        i += r*2
        rr, cc = disk((500, i), r, shape=test_labels.shape)
        test_labels[rr, cc] = 1
    test_labels = label(test_labels)
    
    viewer.add_labels(test_labels)

    my_widget = TableWidget(viewer)

    assert len(my_widget.table._table) == len(np.unique(test_labels)) - 1

