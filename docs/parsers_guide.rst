.. _parsers-guide:

Parsers Guide
=============

Parsers detect events or segment structural boundaries within the current
trace. Each parser analyzes a segment's data and returns a list of (start,
end) boundaries that become child segments in the tree.

There are two categories:

- **Event detectors** — find translocation events within voltage steps:
  ``AutoSquareParser``, ``SpikeParser``, ``lambda_event_parser``.
- **Segmenters** — split existing segments into sub-regions based on
  statistical properties: ``SpeedyStatSplit``, ``FilterDerivativeSegmenter``.
  These are typically applied *within* already-detected events to resolve
  multi-level current states.

How parsing works
-----------------

Call ``segment.parse()`` with a parser object, a rank name for the new
children, and optionally a target rank:

.. code-block:: python

   from ionique.parsers import AutoSquareParser

   detector = AutoSquareParser(threshold_baseline=0.7, expected_conductance=1.9)

   # Detect events within each voltage step
   trace.parse(detector, newrank="event", at_child_rank="vstep")

   # Or parse the trace directly (no at_child_rank)
   trace.parse(detector, newrank="event")

When ``at_child_rank`` is set, ``parse()`` iterates over all children at that
rank and runs the parser on each one. The detected boundaries become children
of the parsed segment.


Choosing a parser
-----------------

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Parser
     - Best for
     - Key parameters
   * - :doc:`AutoSquareParser <parsers/autosquare_parser>`
     - Square-pulse protein blockades
     - ``threshold_baseline``, ``expected_conductance``
   * - :doc:`SpikeParser <parsers/spike_parser>`
     - Brief spike-like events
     - ``height``, ``prominence``, ``distance``, ``width``
   * - :doc:`SpeedyStatSplit <parsers/speedy_statsplit>`
     - Sub-state segmentation within events
     - ``min_width``, ``window_width``, ``false_positive_rate``
   * - :doc:`Other parsers <parsers/other_parsers>`
     - Specialized tasks
     - See individual pages

**Quick decision guide:**

*Step 1 — detect events:*

- Signal has **rectangular blockades** with known conductance → AutoSquareParser
- Signal has **brief downward spikes** → SpikeParser
- Need a **simple threshold rule** → lambda_event_parser

*Step 2 (optional) — segment within events:*

- Events have **multi-level current sub-states** → SpeedyStatSplit

*Utilities:*

- Need to **exclude time regions** → ExclusionParser
- Need to **separate noisy from clean regions** → NoiseFilterParser
- Building **IV curves** → IVCurveParser + IVCurveAnalyzer


Chaining parsers
----------------

You can apply parsers at successively deeper ranks. A typical three-stage
pipeline: filter noisy regions, detect events, then segment sub-states:

.. code-block:: python

   from ionique.parsers import NoiseFilterParser, AutoSquareParser, SpeedyStatSplit

   # 1. Separate clean from noisy regions
   noise_parser = NoiseFilterParser(noise_threshold=60, detect_noise=False)
   trace.parse(noise_parser, newrank="clean", at_child_rank="vstep")

   # 2. Detect blockade events in clean regions
   detector = AutoSquareParser(threshold_baseline=0.7, expected_conductance=1.9)
   trace.parse(detector, newrank="event", at_child_rank="clean")

   # 3. Segment sub-states within each event
   splitter = SpeedyStatSplit(sampling_freq=100000, min_width=50)
   trace.parse(splitter, newrank="state", at_child_rank="event")


Parser output format
--------------------

All parsers return a list of tuples: ``(start, end, features_dict)``.
The ``features_dict`` contains parser-specific metadata that gets stored in
each child segment's ``unique_features``.

.. code-block:: python

   # Example: AutoSquareParser returns per-event features
   # (start, end, {"baseline": 1.8, "frac": 0.62, "mean": 1.12, "wrap": ...})


Saving and loading parsers
--------------------------

Parsers support JSON serialization for reproducibility:

.. code-block:: python

   # Save configuration to file
   parser.to_json(filename="my_parser.json")

   # Get JSON string without saving to file
   json_str = parser.to_json()

.. note::
   ``from_json`` is defined but not yet fully implemented. Parser
   restoration from JSON will be available in a future release.

.. toctree::
   :maxdepth: 1
   :caption: Parser deep-dives

   parsers/spike_parser
   parsers/speedy_statsplit
   parsers/autosquare_parser
   parsers/other_parsers
