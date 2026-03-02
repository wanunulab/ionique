.. _parsers-guide:

Parsers Guide
=============

Parsers detect events or structural boundaries within segments. Each parser
analyzes the current data of a segment and returns a list of (start, end)
boundaries that become child segments in the tree.

How parsing works
-----------------

Call ``segment.parse()`` with a parser object, a rank name for the new
children, and optionally a target rank:

.. code-block:: python

   from ionique.parsers import SpeedyStatSplit

   parser = SpeedyStatSplit(sampling_freq=100000, min_width=50)

   # Parse events within each voltage step
   trace.parse(parser, newrank="event", at_child_rank="vstep")

   # Or parse the trace directly (no at_child_rank)
   trace.parse(parser, newrank="event")

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
   * - :doc:`SpeedyStatSplit <parsers/speedy_statsplit>`
     - Multi-level blockades, general segmentation
     - ``min_width``, ``window_width``, ``false_positive_rate``
   * - :doc:`SpikeParser <parsers/spike_parser>`
     - Brief spike-like events
     - ``height``, ``prominence``, ``distance``, ``width``
   * - :doc:`AutoSquareParser <parsers/autosquare_parser>`
     - Square-pulse protein blockades
     - ``threshold_baseline``, ``expected_conductance``
   * - :doc:`Other parsers <parsers/other_parsers>`
     - Specialized tasks
     - See individual pages

**Quick decision guide:**

- Signal has **multi-level current states** → SpeedyStatSplit
- Signal has **brief downward spikes** → SpikeParser
- Signal has **rectangular blockades** with known conductance → AutoSquareParser
- Need to **exclude time regions** → ExclusionParser
- Need to **separate noisy from clean regions** → NoiseFilterParser
- Building **IV curves** → IVCurveParser + IVCurveAnalyzer


Chaining parsers
----------------

You can apply parsers at successively deeper ranks:

.. code-block:: python

   from ionique.parsers import NoiseFilterParser, SpeedyStatSplit

   # First: separate clean from noisy regions
   noise_parser = NoiseFilterParser(noise_threshold=60, detect_noise=False)
   trace.parse(noise_parser, newrank="clean", at_child_rank="vstep")

   # Then: detect events only in clean regions
   event_parser = SpeedyStatSplit(sampling_freq=100000, min_width=50)
   trace.parse(event_parser, newrank="event", at_child_rank="clean")


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

   # Save configuration
   json_str = parser.to_json("my_parser.json")

   # Reload
   from ionique.parsers import Parser
   restored = Parser.from_json(json_str)

.. toctree::
   :maxdepth: 1
   :caption: Parser deep-dives

   parsers/spike_parser
   parsers/speedy_statsplit
   parsers/autosquare_parser
   parsers/other_parsers
