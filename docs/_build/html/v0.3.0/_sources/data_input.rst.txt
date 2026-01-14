Data Input
^^^^^^^^^^^

**File Readers**

Ionique supports multiple file formats commonly utilized in nanopore experiments:

- **.edh** – Element Data Header files containing metadata and pointers to raw data
- **.opt** – Orbit Potential files with recorded current and voltage data
- **.abf** – Axon Binary Format files used by pClamp software
- **.xml** – XML configuration and metadata files associated with experiments

The framework provides specialized reader classes (subclasses of ``AbstractFileReader``) to handle each format’s
structure and extract both metadata and raw signal data.

**File Reading Process**

1. Identify file format based on extension
2. Use the appropriate reader class to extract metadata
3. Load raw current and voltage traces
4. Align voltage to raw current
5. Convert values to standardized SI units
6. Apply optional pre-processing (e.g., downsampling, filtering, trimming)

**Example**

.. code-block:: python

   from ionique.io import EDHReader

   reader = EDHReader("path/to/file.edh", downsample=5)
   metadata, current, voltage = reader