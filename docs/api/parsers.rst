ionique.parsers
===============

The ``parsers`` module provides event detection algorithms for ionic current
data. All parsers subclass ``Parser`` and implement a ``parse()`` method that
returns boundary tuples.

**Variance-based segmentation:**

- ``SpeedyStatSplit`` — recursive variance splitting (Cython-accelerated)

**Peak/spike detection:**

- ``SpikeParser`` — scipy.signal.find_peaks wrapper with fractional scaling

**Threshold-based detection:**

- ``AutoSquareParser`` — square-pulse blockade detector
- ``lambda_event_parser`` — simple threshold with rule-based filtering
- ``snakebase_parser`` — peak-to-peak amplitude segmentation

**Signal classification:**

- ``NoiseFilterParser`` — classifies clean vs noisy regions
- ``FilterDerivativeSegmenter`` — derivative threshold segmentation

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
