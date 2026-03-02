.. _ionique:

ionique: Nanopore Signal Analysis
==================================

ionique is a Python framework for processing ionic current data from nanopore
experiments. It provides a unified workflow for loading raw traces, filtering
noise, detecting translocation events, and extracting features — all built
around a flexible tree-based segment hierarchy.

.. code-block:: python

   from ionique.io import EDHReader
   from ionique.datatypes import TraceFile
   from ionique.parsers import SpeedyStatSplit
   from ionique.utils import Filter, extract_features

   # Load a nanopore recording
   reader = EDHReader("experiment.edh", voltage_compress=True)
   trace = TraceFile(*reader)

   # Filter noise
   filt = Filter(cutoff_frequency=5000, filter_type="lowpass", sampling_frequency=100000)
   filt(trace.current)

   # Detect events in each voltage step
   parser = SpeedyStatSplit(sampling_freq=100000, min_width=50)
   trace.parse(parser, newrank="event", at_child_rank="vstep")

   # Extract features to a DataFrame
   df = extract_features(trace, "event", ["mean", "std", "duration"])

Key capabilities:

- **File I/O** — Read ``.edh``, ``.opt``, and ``.abf`` formats with automatic
  unit scaling and voltage-step detection.
- **Signal preprocessing** — Lowpass/highpass/bandpass filtering, clock-tone
  removal, and edge trimming.
- **Event detection** — 10+ parsers including variance-based splitting
  (SpeedyStatSplit), spike detection (SpikeParser), and square-pulse analysis
  (AutoSquareParser).
- **Segment tree** — Hierarchical data model (file → voltage step → event)
  with recursive parsing, feature lookup, and memory-efficient MetaSegments.
- **Feature extraction** — Export segment statistics to pandas DataFrames with
  custom computed columns.
- **Visualization** — Quick trace plotting with ``qp_trace()`` and interactive
  Panel/Bokeh dashboards.


.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   install_beginner
   ionique_starter
   python_vscode_start

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   getting_started
   data_input
   concepts
   signal_preprocess
   parsers_guide
   signal_analysis
   visualization
   tutorial

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api_reference


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
