ionique.parsers
===============

The ``parsers`` module provides event detection and signal segmentation
algorithms for ionic current data. All parsers subclass ``Parser`` and
implement a ``parse()`` method that returns boundary tuples.

**Event detectors** — find translocation events within voltage steps:

- ``AutoSquareParser`` — square-pulse blockade detector
- ``SpikeParser`` — scipy.signal.find_peaks wrapper with fractional scaling
- ``lambda_event_parser`` — simple threshold with rule-based filtering
- ``snakebase_parser`` — peak-to-peak amplitude segmentation

**Sub-state segmenters** — split already-detected events into current levels:

- ``SpeedyStatSplit`` — recursive variance splitting (Cython-accelerated)
- ``FilterDerivativeSegmenter`` — derivative threshold segmentation

**Signal classification:**

- ``NoiseFilterParser`` — classifies clean vs noisy regions

**IV analysis:**

- ``IVCurveParser`` — voltage protocol pattern matching
- ``IVCurveAnalyzer`` — mean current per voltage level

**Utilities:**

- ``ExclusionParser`` — excludes time regions
- ``MemoryParse`` — reconstructs segments from saved boundaries

See the :doc:`/parsers_guide` for usage examples and parameter tuning.

.. automodule:: ionique.parsers
   :members:
   :undoc-members:
   :show-inheritance:
