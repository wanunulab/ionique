.. _other-parsers:

Other Parsers
=============

This page covers ionique's specialized parsers. Each is briefly described
with its parameters and a usage example.


FilterDerivativeSegmenter
-------------------------

Detects segment boundaries using the derivative of a lowpass-filtered signal.
Sharp transitions produce large derivative values that cross a threshold.

.. image:: /_static/images/parsers/other/filter_derivative.png
   :alt: FilterDerivativeSegmenter — filtered signal and its derivative
   :width: 100%

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Parameter
     - Default
     - Description
   * - ``low_threshold``
     - ``1``
     - Lower derivative threshold for transition detection.
   * - ``high_threshold``
     - ``2``
     - Upper derivative threshold.
   * - ``cutoff_freq``
     - ``1000.0``
     - Lowpass cutoff (Hz) applied before derivative computation.
   * - ``sampling_freq``
     - ``1e5``
     - Sampling frequency (Hz).

.. code-block:: python

   from ionique.parsers import FilterDerivativeSegmenter

   parser = FilterDerivativeSegmenter(
       low_threshold=1.5,
       high_threshold=3.0,
       cutoff_freq=2000,
       sampling_freq=100000,
   )
   trace.parse(parser, newrank="event", at_child_rank="vstep")


NoiseFilterParser
-----------------

Classifies signal regions as clean or noisy based on local variance. Useful
for excluding unstable portions of a trace before event detection.

.. image:: /_static/images/parsers/other/noise_filter.png
   :alt: NoiseFilterParser — clean vs noisy regions
   :width: 100%

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Parameter
     - Default
     - Description
   * - ``noise_threshold``
     - ``60``
     - Variance threshold for noise classification.
   * - ``detect_noise``
     - ``True``
     - If ``True``, returns noisy regions. If ``False``, returns clean
       regions.

.. code-block:: python

   from ionique.parsers import NoiseFilterParser

   # Keep only clean regions
   parser = NoiseFilterParser(noise_threshold=60, detect_noise=False)
   trace.parse(parser, newrank="clean", at_child_rank="vstep")

   # Then parse events in clean regions only
   trace.parse(event_parser, newrank="event", at_child_rank="clean")


snakebase_parser
----------------

Segments the signal based on peak-to-peak amplitude changes. Detects regions
where the local amplitude exceeds a threshold.

.. image:: /_static/images/parsers/other/snakebase.png
   :alt: snakebase_parser — peak-to-peak amplitude segmentation
   :width: 100%

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Parameter
     - Default
     - Description
   * - ``threshold``
     - ``1.5``
     - Amplitude threshold for segmentation.

.. code-block:: python

   from ionique.parsers import snakebase_parser

   parser = snakebase_parser(threshold=1.5)
   trace.parse(parser, newrank="event", at_child_rank="vstep")


ExclusionParser
---------------

Excludes specified time regions from analysis. The remaining (non-excluded)
portions become child segments.

.. image:: /_static/images/parsers/other/exclusion.png
   :alt: ExclusionParser — excluding time regions
   :width: 100%

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Parameter
     - Default
     - Description
   * - ``regions``
     - (required)
     - List of ``(start_sec, end_sec)`` tuples specifying time intervals to
       exclude.

.. code-block:: python

   from ionique.parsers import ExclusionParser

   # Exclude two noisy time windows
   parser = ExclusionParser(regions=[
       (0.2, 0.4),    # exclude 0.2–0.4 seconds
       (1.2, 1.4),    # exclude 1.2–1.4 seconds
   ])
   trace.parse(parser, newrank="clean", at_child_rank="vstep")


lambda_event_parser
-------------------

A rule-based parser that detects events using a simple threshold and optional
filtering rules.

.. image:: /_static/images/parsers/other/lambda_parser.png
   :alt: lambda_event_parser — threshold-based detection
   :width: 100%

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Parameter
     - Default
     - Description
   * - ``threshold``
     - ``90``
     - Current threshold for event detection (as percentage of baseline).
   * - ``rules``
     - ``None``
     - List of callable rules for post-filtering.

.. code-block:: python

   from ionique.parsers import lambda_event_parser

   parser = lambda_event_parser(threshold=85)
   trace.parse(parser, newrank="event", at_child_rank="vstep")


IVCurveParser and IVCurveAnalyzer
---------------------------------

These two classes work together to extract current–voltage (IV)
relationships from multi-voltage-step recordings.

.. image:: /_static/images/parsers/other/iv_curve.png
   :alt: IV curve — current vs voltage
   :width: 60%
   :align: center

**IVCurveParser** identifies the voltage protocol pattern:

.. code-block:: python

   from ionique.parsers import IVCurveParser

   parser = IVCurveParser(voltage_array)
   patterns = parser.parse()
   # Returns matched voltage patterns for IV analysis

**IVCurveAnalyzer** computes mean current at each voltage level:

.. code-block:: python

   from ionique.parsers import IVCurveAnalyzer

   analyzer = IVCurveAnalyzer(
       current=current_array,
       parent_segment=vstep,
       sampling_frequency=100000,
       method="simple",
   )
   iv_data = analyzer.analyze()
   # Returns {voltage_value: (mean_current, std_current), ...}


MemoryParse
-----------

Reconstructs segments from precomputed boundaries. Useful for loading
previously saved analysis results.

.. code-block:: python

   from ionique.parsers import MemoryParse

   parser = MemoryParse(
       starts=[1000, 3000, 7000],
       ends=[1500, 3800, 7200],
   )
   trace.parse(parser, newrank="event", at_child_rank="vstep")
