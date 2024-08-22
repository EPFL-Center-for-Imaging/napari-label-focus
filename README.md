![EPFL Center for Imaging logo](https://imaging.epfl.ch/resources/logo-for-gitlab.svg)
# napari-label-focus

Easily focus the view on selected elements from a **Labels** layer to inspect them.

- The plugin works on 2D, 2D+time, 3D, and 4D images.
- The table shows the label index and volume (number of pixels) of each label.
- Click on the table rows to focus the view on the corresponding label.
- The table is updated when layers are added or removed from the viewer, selected from the dropdown, and when their data is modified.
- The table is sorted by volume (biggest object on top).
- You can save the table as a CSV file.

<p align="center">
    <img src="assets/gif01.gif" height="400">
</p>

----------------------------------

This [napari] plugin was generated with [Cookiecutter] using [@napari]'s [cookiecutter-napari-plugin] template.

## Installation

You can install `napari-label-focus` via [pip]:

    pip install napari-label-focus

## Contributing

Contributions are very welcome. Tests can be run with [tox], please ensure
the coverage at least stays the same before you submit a pull request.

## License

Distributed under the terms of the [BSD-3] license,
"napari-label-focus" is free and open source software

## Issues

If you encounter any problems, please file an issue along with a detailed description.

----------------------------------

This [napari] plugin is an output of a collaborative project between the [EPFL Center for Imaging](https://imaging.epfl.ch/) and the [De Palma Lab](https://www.epfl.ch/labs/depalma-lab/) in 2023.

[napari]: https://github.com/napari/napari
[Cookiecutter]: https://github.com/audreyr/cookiecutter
[@napari]: https://github.com/napari
[MIT]: http://opensource.org/licenses/MIT
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
[GNU GPL v3.0]: http://www.gnu.org/licenses/gpl-3.0.txt
[GNU LGPL v3.0]: http://www.gnu.org/licenses/lgpl-3.0.txt
[Apache Software License 2.0]: http://www.apache.org/licenses/LICENSE-2.0
[Mozilla Public License 2.0]: https://www.mozilla.org/media/MPL/2.0/index.txt
[cookiecutter-napari-plugin]: https://github.com/napari/cookiecutter-napari-plugin

[napari]: https://github.com/napari/napari
[tox]: https://tox.readthedocs.io/en/latest/
[pip]: https://pypi.org/project/pip/
[PyPI]: https://pypi.org/
