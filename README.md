# ionique

[![Pylint](https://github.com/wanunulab/ionique/actions/workflows/pylint.yml/badge.svg)](https://github.com/wanunulab/ionique/actions/workflows/pylint.yml)
[![Pytest](https://github.com/wanunulab/ionique/actions/workflows/pytest.yml/badge.svg)](https://github.com/wanunulab/ionique/actions/workflows/pytest.yml)
[![Documentation](https://readthedocs.org/projects/ionique/badge/?version=latest)](https://ionique.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modular nanopore signal analysis framework for ionic current data. Load recordings, filter noise, detect translocation events, segment sub-states, and extract features — all through a composable Python API or an interactive GUI.

Built for experimentalists who need custom analysis workflows without writing everything from scratch.

## Quick start

```python
from ionique.io import EDHReader
from ionique.datatypes import TraceFile
from ionique.parsers import AutoSquareParser
from ionique.utils import Filter, Trimmer, extract_features

# Load and preprocess
metadata, current, voltage = EDHReader("experiment.edh", voltage_compress=True)
trace = TraceFile(current, voltage=voltage, metadata=metadata)
Filter(cutoff_frequency=5000, filter_type="lowpass",
       sampling_frequency=trace.sampling_freq)(trace.current)
Trimmer(samples_to_remove=500)(trace)

# Detect events and extract features
detector = AutoSquareParser(threshold_baseline=0.7, expected_conductance=1.9)
trace.parse(detector, newrank="event", at_child_rank="vstepgap")
df = extract_features(trace, "event", ["mean", "std", "duration"])
```

## Features

- **File I/O** — read EDH, OPT, and ABF nanopore recordings
- **Signal preprocessing** — lowpass/highpass/bandpass filtering, clock interference removal, voltage-step edge trimming
- **Event detection** — AutoSquareParser for rectangular blockades, SpikeParser for brief spikes, lambda_event_parser for simple thresholds
- **Sub-state segmentation** — SpeedyStatSplit (Cython-accelerated) resolves multi-level current structure within events
- **Feature extraction** — export event statistics to pandas DataFrames
- **Visualization** — quick-plot traces with `qp_trace()`, interactive dashboards with Panel/Bokeh
- **GUI workflows** — Panel widgets for loading files, configuring parsers, and inspecting events in Jupyter

## Installation

Python 3.10–3.13. Requires a C compiler for the Cython extension. 
To get the latest release:

```bash
pip install ionique
```

For latest unreleased version directly from GitHub:

```bash
pip install git+https://github.com/wanunulab/ionique.git
```

For development:

```bash
git clone https://github.com/wanunulab/ionique.git
cd ionique
pip install -e .
```

For GUI/dashboard features (Panel, Bokeh):

```bash
pip install ionique[panel]
```

Or in a development install:

```bash
pip install -e ".[panel]"
```

## Documentation

Full user guide, tutorials, and API reference at **[ionique.readthedocs.io](https://ionique.readthedocs.io/)**.

## License

MIT License — see [LICENSE](LICENSE) for details.

&copy; 2026 The Wanunu Lab.
