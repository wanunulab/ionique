ionique.io
==========

The ``io`` module provides file readers for nanopore data formats. All readers
subclass ``AbstractFileReader`` and return ``(metadata, current, voltage)``
tuples.

- ``EDHReader`` — Element Data Header files (``.edh``)
- ``OPTReader`` — Orbit Potential files (``.opt``)
- ``ABFReader`` — Axon Binary Format files (``.abf``)

See :doc:`/data_input` for usage examples.

.. automodule:: ionique.io
   :members:
   :undoc-members:
   :show-inheritance:
