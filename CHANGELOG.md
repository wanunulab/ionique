# Changelog

All notable changes to ionique will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.4.0] — 2026-03-02

First official release of ionique — a modular nanopore signal analysis
framework for ionic current data processing.

### Core framework

- Tree-based segment hierarchy (`AbstractSegmentTree`, `Segment`,
  `MetaSegment`) for representing nested slices of current traces
- Recursive parsing: `parse()` subdivides segments into children at named
  ranks (file → vstep → event → state)
- Tree traversal: `traverse_to_rank()`, `climb_to_rank()`, `get_feature()`
- JSON serialization and deserialization of segment trees
- Feature extraction to pandas DataFrames via `extract_features()`

### File I/O

- `EDHReader` — Axon/EDH binary format with voltage-step splitting
- `OPTReader` — OPT format with downsampling and pre-filtering
- `ABFReader` — Axon Binary Format (ABF) via pyabf
- `SessionFileManager` singleton for managing loaded files

### Event detection

- `AutoSquareParser` — square-pulse blockade detector with configurable
  threshold and conductance
- `SpikeParser` — scipy `find_peaks` wrapper with fractional scaling for
  brief spike-like events
- `lambda_event_parser` — simple threshold-based detection with rule
  filtering

### Sub-state segmentation

- `SpeedyStatSplit` — Cython-accelerated recursive variance splitting for
  resolving multi-level current states within events
- `FilterDerivativeSegmenter` — derivative-threshold segmentation

### Signal preprocessing

- `Filter` — configurable Butterworth/Bessel lowpass, highpass, bandpass,
  and bandstop filtering (uni- or bidirectional)
- `ClockFilter` — targeted removal of periodic electrical interference at a
  known clock frequency and its harmonics
- `Trimmer` — removes edge samples from voltage steps to discard capacitive
  transients

### Other parsers and utilities

- `NoiseFilterParser` — classifies clean vs noisy signal regions
- `ExclusionParser` — excludes user-specified time regions
- `IVCurveParser` / `IVCurveAnalyzer` — voltage protocol matching and
  per-voltage mean current extraction for IV curves
- `snakebase_parser` — peak-to-peak amplitude segmentation
- `MemoryParse` — reconstructs segments from saved boundaries

### Visualization

- `qp_trace()` — Bokeh-based quick-plot with multi-rank overlay,
  downsampling, and voltage display options
- Panel-based interactive dashboards for GUI workflows
- `simple.py` — Jupyter/Panel convenience functions for non-programmers

### Documentation

- Comprehensive user guide: quickstart, data input, core concepts, signal
  preprocessing, parser guide with parameter sensitivity galleries, signal
  analysis, visualization, and end-to-end tutorial
- Pre-generated figures from synthetic data (no ionique import needed at
  build time)
- Full API reference with autodoc
- Hosted on Read the Docs
