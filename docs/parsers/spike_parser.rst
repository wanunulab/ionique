.. _spike-parser:

SpikeParser
===========

``SpikeParser`` detects brief spike-like events in ionic current traces. It
wraps ``scipy.signal.find_peaks`` and interprets parameters as fractions of
the signal mean when ``fractional=True`` (the default).

.. code-block:: python

   from ionique.parsers import SpikeParser

   parser = SpikeParser(
       prominence=0.15,
       distance=100,
       width=(5, 200),
       fractional=True,
   )
   trace.parse(parser, newrank="event", at_child_rank="vstep")


Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Default
     - Description
   * - ``height``
     - ``None``
     - Minimum spike height. When ``fractional=True``, interpreted as a
       fraction of the segment mean.
   * - ``threshold``
     - ``None``
     - Minimum vertical distance to neighboring samples.
   * - ``distance``
     - ``None``
     - Minimum horizontal distance (in samples) between peaks.
   * - ``prominence``
     - ``None``
     - Minimum peak prominence — how much a peak stands out from its
       surroundings. This is usually the most important parameter.
   * - ``prominence_snr``
     - ``None``
     - SNR-based prominence (alternative to ``prominence``).
   * - ``width``
     - ``None``
     - Required peak width. Pass a tuple ``(min, max)`` to filter by width.
   * - ``wlen``
     - ``None``
     - Window length for prominence calculation.
   * - ``rel_height``
     - ``0.5``
     - Relative height at which width is measured (0–1).
   * - ``plateu_size``
     - ``None``
     - Minimum flat-top length for plateau detection.
   * - ``fractional``
     - ``True``
     - When ``True``, ``height``, ``threshold``, ``prominence``, and
       ``distance`` are scaled by the segment mean.


Parameter sensitivity
---------------------

The figures below show how each parameter affects detection on the same
synthetic spike signal.

height
^^^^^^

Controls the minimum absolute (or fractional) spike amplitude. Lower values
detect smaller events; higher values miss shallow dips.

.. image:: /_static/images/parsers/spike/height_comparison.png
   :alt: SpikeParser height parameter comparison
   :width: 100%

prominence
^^^^^^^^^^

Prominence measures how much a peak stands out relative to its surrounding
baseline. This is generally the single most useful parameter for nanopore
spike detection.

.. image:: /_static/images/parsers/spike/prominence_comparison.png
   :alt: SpikeParser prominence parameter comparison
   :width: 100%

distance
^^^^^^^^

Minimum spacing between detected peaks (in samples). Increase this to prevent
detecting multiple hits on a single wide event.

.. image:: /_static/images/parsers/spike/distance_comparison.png
   :alt: SpikeParser distance parameter comparison
   :width: 100%

width
^^^^^

Filter by peak width. Pass a tuple ``(min_width, max_width)`` to reject
events that are too narrow (noise) or too wide (baseline drift).

.. image:: /_static/images/parsers/spike/width_comparison.png
   :alt: SpikeParser width parameter comparison
   :width: 100%


Full example
------------

.. image:: /_static/images/parsers/spike/full_example.png
   :alt: SpikeParser full detection example
   :width: 100%

.. code-block:: python

   from ionique.parsers import SpikeParser

   parser = SpikeParser(
       prominence=0.15,
       distance=100,
       width=(1, 200),
       fractional=True,
   )

   trace.parse(parser, newrank="event", at_child_rank="vstep")

   events = trace.traverse_to_rank("event")
   print(f"Detected {len(events)} spike events")

   for ev in events[:5]:
       print(f"  samples {ev.start}–{ev.end}, mean={ev.mean:.3f} nA")


Tips
----

- Start with ``prominence`` only, then add ``distance`` and ``width`` to
  refine.
- Set ``fractional=False`` if you know the absolute current scale and want
  to specify parameters in nanoamperes directly.
- For very noisy data, lowpass-filter first (see :doc:`/signal_preprocess`),
  then use a moderate ``prominence``.
