.. _autosquare-parser:

AutoSquareParser
================

``AutoSquareParser`` detects rectangular (square-pulse) blockade events —
the signature of protein or polymer translocations through nanopores. It
identifies regions where current drops below a threshold fraction of the
open-channel baseline.

.. code-block:: python

   from ionique.parsers import AutoSquareParser

   parser = AutoSquareParser(
       threshold_baseline=0.7,
       expected_conductance=1.9,
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
   * - ``threshold_baseline``
     - ``0.7``
     - Fraction of baseline current that defines an event. A value of 0.7
       means any region below 70% of baseline is considered a blockade.
   * - ``expected_conductance``
     - ``1.9``
     - Expected open-channel conductance in nS. Used to validate that the
       baseline is reasonable.
   * - ``conductance_tolerance``
     - ``1.2``
     - Multiplicative tolerance for conductance validation.
   * - ``wrap_padding``
     - ``50``
     - Number of context samples to include before and after each detected
       event (stored in ``unique_features["wrap"]``).
   * - ``rules``
     - ``[]``
     - List of callable rules for post-filtering events. Each rule takes a
       segment dict and returns ``True`` to keep it.

The parser also requires ``eff_sampling_freq`` and ``voltage`` to be
available (passed automatically when parsing within a TraceFile tree).


Parameter sensitivity
---------------------

threshold_baseline
^^^^^^^^^^^^^^^^^^

The most important parameter. Lower values require deeper blockades to
trigger detection; higher values detect shallower events (but may pick up
noise).

.. image:: /_static/images/parsers/autosquare/threshold_comparison.png
   :alt: AutoSquareParser threshold_baseline comparison
   :width: 100%

.. code-block:: python

   # Sensitive: detect shallow blockades
   parser = AutoSquareParser(threshold_baseline=0.9)

   # Strict: only detect deep blockades
   parser = AutoSquareParser(threshold_baseline=0.5)

expected_conductance
^^^^^^^^^^^^^^^^^^^^

Used to validate that the open-channel baseline is physically reasonable.
Set this to match your nanopore's conductance (typically 1–5 nS for solid-
state pores).

.. image:: /_static/images/parsers/autosquare/conductance_comparison.png
   :alt: AutoSquareParser expected_conductance comparison
   :width: 100%


Using rules for post-filtering
------------------------------

The ``rules`` parameter accepts lambda functions that filter events after
detection. Each rule receives a dictionary with event properties and returns
``True`` to keep the event:

.. code-block:: python

   parser = AutoSquareParser(
       threshold_baseline=0.7,
       expected_conductance=1.9,
       rules=[
           lambda ev: ev["frac"] < 0.9,        # blockade must be >10% of baseline
           lambda ev: (ev["end"] - ev["start"]) > 50,  # minimum 50 samples
       ],
   )


Full example
------------

.. image:: /_static/images/parsers/autosquare/full_example.png
   :alt: AutoSquareParser full detection example
   :width: 100%

.. code-block:: python

   from ionique.parsers import AutoSquareParser

   parser = AutoSquareParser(
       threshold_baseline=0.7,
       expected_conductance=1.9,
       wrap_padding=100,
   )

   trace.parse(parser, newrank="event", at_child_rank="vstep")

   events = trace.traverse_to_rank("event")
   print(f"Detected {len(events)} blockade events")

   for ev in events[:5]:
       baseline = ev.unique_features.get("baseline", None)
       frac = ev.unique_features.get("frac", None)
       print(f"  [{ev.start}:{ev.end}] baseline={baseline:.3f}, I/I0={frac:.3f}")


Per-event features
------------------

``AutoSquareParser`` stores additional metadata in each event's
``unique_features``:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Description
   * - ``baseline``
     - Open-channel current before the blockade (nA).
   * - ``mean``
     - Mean current during the blockade (nA).
   * - ``frac``
     - Fractional blockade depth: ``mean / baseline``.
   * - ``wrap``
     - Context window around the event (numpy array with padding).
