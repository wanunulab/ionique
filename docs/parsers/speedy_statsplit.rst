.. _speedy-statsplit:

SpeedyStatSplit
===============

``SpeedyStatSplit`` is a variance-based recursive segmentation algorithm
optimized in Cython. It finds boundaries where the signal's statistical
properties change — making it ideal for multi-level blockade detection.

The algorithm recursively splits a signal at the point that maximizes the
reduction in total variance, stopping when segments are too narrow or the
gain is below a threshold.

.. code-block:: python

   from ionique.parsers import SpeedyStatSplit

   parser = SpeedyStatSplit(
       sampling_freq=100000,
       min_width=100,
       window_width=10000,
   )
   trace.parse(parser, newrank="event", at_child_rank="vstep")


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

   # Fine-grained: detect short events
   parser = SpeedyStatSplit(sampling_freq=100000, min_width=50)

   # Coarse: only detect long-duration states
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

   # High sensitivity — detect small, brief transitions
   parser = SpeedyStatSplit(
       sampling_freq=100000,
       min_width=50,
       false_positive_rate=10.0,
   )

   # Low sensitivity — only detect large, clear transitions
   parser = SpeedyStatSplit(
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

   from ionique.parsers import SpeedyStatSplit

   parser = SpeedyStatSplit(
       sampling_freq=100000,
       min_width=200,
       window_width=10000,
   )

   trace.parse(parser, newrank="event", at_child_rank="vstep")

   events = trace.traverse_to_rank("event")
   print(f"Detected {len(events)} segments")

   for ev in events[:5]:
       print(f"  [{ev.start}:{ev.end}] mean={ev.mean:.3f}, std={ev.std:.4f}")


Additional methods
------------------

``SpeedyStatSplit`` exposes lower-level methods through its Cython backend:

.. code-block:: python

   # Get MetaSegment objects directly (more memory-efficient)
   segments = parser.parse_meta(current_array)

   # Find the single best split point
   best_index = parser.best_single_split(current_array)

.. tip::
   For very long traces (>1M samples), consider splitting by voltage step
   first (``at_child_rank="vstep"``), then running SpeedyStatSplit on each
   step. This is both faster and uses less memory.
