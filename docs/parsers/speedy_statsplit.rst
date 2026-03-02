.. _speedy-statsplit:

SpeedyStatSplit
===============

``SpeedyStatSplit`` is a variance-based recursive segmentation algorithm
optimized in Cython. It finds boundaries where the signal's statistical
properties change — making it ideal for resolving **multi-level current
sub-states within already-detected events**.

.. note::
   SpeedyStatSplit is **not** an event detector. Use an event detector
   (``AutoSquareParser``, ``SpikeParser``, or ``lambda_event_parser``) first
   to find translocation events, then apply SpeedyStatSplit to segment
   current levels within those events.

The algorithm recursively splits a signal at the point that maximizes the
reduction in total variance, stopping when segments are too narrow or the
gain is below a threshold.

**Typical two-stage workflow:**

.. code-block:: python

   from ionique.parsers import AutoSquareParser, SpeedyStatSplit

   # Stage 1: detect blockade events
   detector = AutoSquareParser(threshold_baseline=0.7, expected_conductance=1.9)
   trace.parse(detector, newrank="event", at_child_rank="vstep")

   # Stage 2: segment sub-states within each event
   splitter = SpeedyStatSplit(
       sampling_freq=100000,
       min_width=100,
       window_width=10000,
   )
   trace.parse(splitter, newrank="state", at_child_rank="event")


Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 28 15 57

   * - Parameter
     - Default
     - Description
   * - ``sampling_freq``
     - (required)
     - Sampling frequency in Hz.
   * - ``min_width``
     - ``100``
     - Minimum segment width in samples. Segments shorter than this will not
       be split further. Controls over-segmentation.
   * - ``max_width``
     - ``1000000``
     - Maximum segment width in samples.
   * - ``window_width``
     - ``10000``
     - Sliding window width for split-point search. Larger values detect
       broader features; smaller values detect finer changes.
   * - ``min_gain_per_sample``
     - ``None``
     - Legacy threshold: minimum log-likelihood gain per sample to accept a
       split. Set this or ``false_positive_rate``, not both.
   * - ``false_positive_rate``
     - ``None``
     - Expected false positive splits per second. Automatically calculates
       the gain threshold.
   * - ``prior_segments_per_second``
     - ``None``
     - Prior expected segment rate for Bayesian threshold calculation.
   * - ``cutoff_freq``
     - ``None``
     - Apply a lowpass filter at this frequency before splitting.


Parameter sensitivity
---------------------

min_width
^^^^^^^^^

Controls the minimum size of detected segments. Small values allow
fine-grained splitting but risk over-segmentation on noise. Large values
merge adjacent states.

.. image:: /_static/images/parsers/speedy/min_width_comparison.png
   :alt: SpeedyStatSplit min_width parameter comparison
   :width: 100%

.. code-block:: python

   # Fine-grained: resolve brief sub-states within events
   parser = SpeedyStatSplit(sampling_freq=100000, min_width=50)

   # Coarse: only detect major current-level changes
   parser = SpeedyStatSplit(sampling_freq=100000, min_width=3000)

window_width
^^^^^^^^^^^^

The window within which split candidates are evaluated. Affects the scale
of detectable transitions.

.. image:: /_static/images/parsers/speedy/window_width_comparison.png
   :alt: SpeedyStatSplit window_width parameter comparison
   :width: 100%

Sensitivity tuning
^^^^^^^^^^^^^^^^^^

The overall sensitivity depends on the interaction between ``min_width`` and
the gain threshold (set via ``false_positive_rate`` or
``min_gain_per_sample``).

.. image:: /_static/images/parsers/speedy/sensitivity_comparison.png
   :alt: SpeedyStatSplit sensitivity comparison
   :width: 100%

.. code-block:: python

   # High sensitivity — resolve small, brief sub-states
   splitter = SpeedyStatSplit(
       sampling_freq=100000,
       min_width=50,
       false_positive_rate=10.0,
   )

   # Low sensitivity — only split on large, clear level changes
   splitter = SpeedyStatSplit(
       sampling_freq=100000,
       min_width=1500,
       false_positive_rate=0.01,
   )


Full example
------------

.. image:: /_static/images/parsers/speedy/full_example.png
   :alt: SpeedyStatSplit full segmentation example
   :width: 100%

.. code-block:: python

   from ionique.parsers import AutoSquareParser, SpeedyStatSplit

   # First detect events
   detector = AutoSquareParser(threshold_baseline=0.7, expected_conductance=1.9)
   trace.parse(detector, newrank="event", at_child_rank="vstep")

   # Then segment sub-states within each event
   splitter = SpeedyStatSplit(
       sampling_freq=100000,
       min_width=200,
       window_width=10000,
   )
   trace.parse(splitter, newrank="state", at_child_rank="event")

   states = trace.traverse_to_rank("state")
   print(f"Resolved {len(states)} sub-states across all events")

   for st in states[:5]:
       print(f"  [{st.start}:{st.end}] mean={st.mean:.3f}, std={st.std:.4f}")


Additional methods
------------------

``SpeedyStatSplit`` exposes lower-level methods through its Cython backend:

.. code-block:: python

   # Get MetaSegment objects directly (more memory-efficient)
   segments = parser.parse_meta(current_array)

   # Find the single best split point
   best_index = parser.best_single_split(current_array)

.. tip::
   SpeedyStatSplit works best on segments that already contain a single
   blockade event with multi-level structure. Running it directly on a
   full voltage step will segment the entire signal (baseline + events
   together), which is usually not what you want. Detect events first,
   then split within them.
