ionique.datatypes
=================

The ``datatypes`` module provides high-level data containers that build on the
segment tree from ``core``.

- ``TraceFile`` — wraps a loaded nanopore recording (current, voltage,
  metadata) as a tree node at rank ``"file"``. Automatically creates voltage-
  step children when voltage boundaries are provided.
- ``SessionFileManager`` — singleton root node that manages all loaded files
  in a session.

See :doc:`/data_input` for usage examples.

.. automodule:: ionique.datatypes
   :members:
   :undoc-members:
   :show-inheritance:
