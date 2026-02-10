ionique.core
============

Overview
--------

The ``core`` module provides the hierarchical segment tree structure used throughout
ionique. It defines classes for representing segments of ionic current data in a
tree hierarchy, where each segment can contain child segments at different "ranks"
(e.g., file → voltage step → event).

Key Concepts
------------

**Segments** represent portions of ionic current traces with start/end indices.

**Ranks** define hierarchy levels. Common ranks include:

- ``"file"`` - The top-level segment containing the entire trace
- ``"vstep"`` - Voltage step segments within a file
- ``"event"`` - Individual events detected within voltage steps

**Parsing** subdivides a segment into children at a new rank using parser objects.

**Feature lookup** traverses up the tree to find attributes (e.g., ``sampling_freq``).

Classes
-------

AbstractSegmentTree
^^^^^^^^^^^^^^^^^^^

The base class providing tree structure and traversal methods. Not typically
instantiated directly.

.. code-block:: python

   from ionique.core import AbstractSegmentTree

   # Tree traversal methods
   segment.traverse_to_rank("event")  # Get all segments at rank "event"
   segment.climb_to_rank("file")      # Go up to find the file-level segment
   segment.get_feature("sampling_freq")  # Look up feature in self or ancestors

MetaSegment
^^^^^^^^^^^

A lightweight segment storing only metadata (start, end, statistics) without
holding the actual current array. Used for memory-efficient storage of parsed results.

**Basic Usage:**

.. code-block:: python

   from ionique.core import MetaSegment

   # Create a metadata segment
   seg = MetaSegment(
       start=1000,
       end=2000,
       rank="event",
       unique_features={"amplitude": 0.5, "dwell_time": 0.01}
   )

   # Access properties
   print(seg.n)       # Length: 1000
   print(seg.start)   # 1000
   print(seg.end)     # 2000

**Accessing Current Data:**

MetaSegment can retrieve current data by climbing to the file-level parent:

.. code-block:: python

   # If seg has a parent chain leading to a file with current data:
   current_slice = seg.current  # Returns current[1000:2000] from file
   print(seg.mean)              # Computes np.mean(current_slice)
   print(seg.std)               # Computes np.std(current_slice)

**Serialization:**

.. code-block:: python

   # Convert to JSON
   json_str = seg.to_json()
   print(json_str)
   # {
   #     "mean": 1.234,
   #     "std": 0.056,
   #     "start": 1000,
   #     "end": 2000,
   #     "name": "MetaSegment"
   # }

   # Convert to dictionary
   seg.to_dict()

Segment
^^^^^^^

A full segment holding the actual current data as a NumPy array. Use this when
you need direct access to the raw signal values.

**Basic Usage:**

.. code-block:: python

   import numpy as np
   from ionique.core import Segment

   # Create sample current data
   current = np.random.randn(1000) * 0.1 + 1.5  # ~1.5 nA with noise

   # Create a segment
   seg = Segment(
       current=current,
       start=0,
       end=1000,
       rank="event"
   )

   # Access statistics (computed on-the-fly)
   print(f"Mean: {seg.mean:.3f}")
   print(f"Std:  {seg.std:.3f}")
   print(f"Min:  {seg.min:.3f}")
   print(f"Max:  {seg.max:.3f}")
   print(f"Length: {seg.n}")

**Converting to MetaSegment:**

To save memory after extracting statistics:

.. code-block:: python

   # Convert to lightweight MetaSegment (deletes current array)
   seg.to_meta()
   # seg is now a MetaSegment with cached mean, std, min, max

Working with the Tree Structure
-------------------------------

**Adding Children:**

.. code-block:: python

   from ionique.core import MetaSegment

   # Create parent segment
   parent = MetaSegment(start=0, end=10000, rank="vstep")

   # Create child segments
   event1 = MetaSegment(start=100, end=500, rank="event", parent=parent)
   event2 = MetaSegment(start=600, end=900, rank="event", parent=parent)

   # Add children to parent
   parent.add_children([event1, event2])

   # Children are automatically sorted by start position
   print(len(parent.children))  # 2

**Traversing the Tree:**

.. code-block:: python

   # Get all segments at a specific rank
   all_events = parent.traverse_to_rank("event")

   # Climb up to find ancestor at a rank
   file_seg = event1.climb_to_rank("file")

   # Get summary of ranks and counts
   summary = parent.summary()
   # {"vstep": 1, "event": 2}

**Looking Up Features:**

Features are looked up in the segment first, then in ancestors:

.. code-block:: python

   # Set a feature at file level
   file_seg.unique_features["sampling_freq"] = 100000

   # Child segments can access it
   event = file_seg.children[0].children[0]  # Some nested event
   freq = event.get_feature("sampling_freq")  # Returns 100000

Parsing Segments
----------------

Use the ``parse()`` method to subdivide segments using parser objects:

.. code-block:: python

   from ionique.parsers import SpikeParser

   # Create a parser
   parser = SpikeParser(
       threshold_start=0.15,
       threshold_end=0.15,
       min_width=10,
       max_width=10000
   )

   # Parse events within each voltage step
   file_segment.parse(
       parser=parser,
       newrank="event",
       at_child_rank="vstep"  # Parse at vstep level, not file level
   )

   # Access detected events
   events = file_segment.traverse_to_rank("event")
   print(f"Detected {len(events)} events")

Utilities
---------

ignored
^^^^^^^

A context manager to suppress specific exceptions (replaces try/except/pass):

.. code-block:: python

   from ionique.core import ignored

   # Instead of:
   try:
       value = some_dict["missing_key"]
   except KeyError:
       pass

   # Use:
   with ignored(KeyError):
       value = some_dict["missing_key"]

   # Can ignore multiple exception types
   with ignored(KeyError, AttributeError):
       value = obj.missing_attr

.. note::
   Segments store references to data arrays, not copies. Modifying the underlying
   array affects all segments referencing it.

.. warning::
   The ``current`` property on ``MetaSegment`` requires a valid parent chain
   up to a file-level segment. It returns ``None`` if the chain is broken.

API Reference
-------------

.. automodule:: ionique.core
   :members:
   :undoc-members:
   :show-inheritance:
