IQ5 Storage
===========

Ionique provides persistent storage via ``.iq5`` files (HDF5-based), allowing
you to save an entire analyzed session (traces, segment trees, annotations) and
reload it later without re-running parsers. Loaded data is backed by lazy disk
access, so accessing ``event.current`` reads only the samples you need from disk
rather than loading the whole file into RAM.

The ``.iq5`` format also supports **purge-to-disk** and **incremental sync**
workflows, where the file acts as a live backing store rather than a snapshot.

This page covers:

- Saving and loading segment trees
- Lazy array access from disk
- Purging to disk to free RAM
- Incremental sync after further parsing
- Managing multiple versions of a trace (raw, filtered, etc.)
- Working with subtrees and individual segments

Saving a Session
----------------

After loading files and running parsers, save the full session (or any
subtree) with :func:`~ionique.storage.save`:

.. code-block:: python

   from ionique.storage import save
   from ionique.datatypes import SessionFileManager, TraceFile
   from ionique.io import OPTReader

   # Set up session and load data
   sfm = SessionFileManager()
   metadata, current, voltage = OPTReader("experiment.opt", voltage_compress=True)
   trace = TraceFile(current=current, voltage=voltage, parent=sfm,
                     unique_features={"sampling_freq": metadata["sampling_freq"]},
                     metadata=metadata)

   # Run parsers ...
   # sfm.parse(parser, newrank="event", at_child_rank="clean")

   # Save the entire session to a single file
   save(sfm, "experiment.iq5")

The ``.iq5`` extension is a convention, not a requirement — any filename works.


Loading a Session
-----------------

Reload a saved file with :func:`~ionique.storage.load`. The returned object
has the same type and tree structure as what was saved, with array data
backed by lazy disk reads:

.. code-block:: python

   from ionique.storage import load

   session = load("experiment.iq5")

   # The tree structure is fully restored
   print(session.summary())
   # {'root': 1, 'file': 2, 'vstep': 8, 'event': 342}

   trace = session.children[0]
   print(trace.metadata)
   # {'experiment': 'NaCl_100mM', ...}

   # Array access reads only the requested slice from disk
   first_1000 = trace.current[0:1000]


Lazy Arrays
-----------

After loading from an ``.iq5`` file, ``trace.current`` and ``trace.time`` are
:class:`~ionique.storage.LazyArray` objects. They behave like numpy arrays
for all practical purposes:

.. code-block:: python

   import numpy as np
   from ionique.storage import load

   trace = load("trace.iq5")

   # Slicing — reads only the requested range from disk
   chunk = trace.current[1000:2000]

   # Standard numpy operations work transparently
   mean_val = np.mean(trace.current)
   std_val = np.std(trace.current)

   # Properties match numpy arrays
   print(trace.current.shape)   # (5000000,)
   print(trace.current.dtype)   # float32
   print(len(trace.current))    # 5000000

   # Convert to a full numpy array when needed
   full_array = np.asarray(trace.current)

MetaSegment access works unchanged — ``event.current`` climbs to the
parent TraceFile and slices the LazyArray:

.. code-block:: python

   events = trace.traverse_to_rank("event")
   event = events[0]

   # These all read only the event's slice from disk
   print(event.mean)
   print(event.std)
   print(event.current)  # numpy array of ~300 samples


Purging to Disk
---------------

The ``to_iq5()`` method saves the tree and replaces in-memory numpy arrays
with lazy disk-backed reads, freeing RAM while keeping the tree usable:

.. code-block:: python

   # Load raw data, parse events
   trace = TraceFile(current=big_array, voltage=voltage, ...)
   sfm.parse(parser, newrank="event", at_child_rank="clean")

   # Purge to disk — RAM freed, tree backed by .iq5
   sfm.to_iq5("experiment.iq5")

   # Data is still accessible via lazy reads
   events = trace.traverse_to_rank("event")
   events[0].mean   # reads ~300 samples from disk

   # Check the backing file path
   print(sfm.iq5_path)  # "experiment.iq5"


Incremental Sync
----------------

After purging to disk, you can continue parsing new ranks and then write
only the new/changed nodes back to the file with ``sync_iq5()``:

.. code-block:: python

   # Parse new ranks after purge
   sfm.parse(new_parser, newrank="subevent", at_child_rank="event")

   # Write only the new subevent nodes to the .iq5 file
   sfm.sync_iq5()

This also works after loading an existing ``.iq5`` file:

.. code-block:: python

   session = load("experiment.iq5")
   session.parse(parser, newrank="subevent", at_child_rank="event")
   session.sync_iq5()   # appends new nodes to the same file

When children are cleared and re-parsed, ``sync_iq5()`` removes the old
children from the file and writes the new ones:

.. code-block:: python

   vstep = trace.children[0]
   vstep.clear_children()  # old event nodes tracked for deletion
   vstep.parse(better_parser, newrank="event")
   sfm.sync_iq5()  # old events deleted, new events written


Detaching from Disk
-------------------

To pull all data back into RAM and disconnect from the ``.iq5`` file:

.. code-block:: python

   session.detach_iq5()

   # Data is now in-memory numpy arrays
   print(type(trace.current))  # <class 'numpy.ndarray'>
   print(session.iq5_path)     # None


Saving and Loading Subtrees
---------------------------

``save()`` and ``load()`` work on any node in the segment hierarchy, not
just the session root. This is useful for sharing individual traces or
voltage steps:

.. code-block:: python

   from ionique.storage import save, load

   # Save a single trace file
   save(trace, "single_trace.iq5")

   # Save one voltage step with all its parsed events
   vstep = trace.traverse_to_rank("vstep")[0]
   save(vstep, "vstep_0.iq5")

   # Save a lone MetaSegment (no array data, just metadata)
   event = trace.traverse_to_rank("event")[0]
   save(event, "event_42.iq5")

   # Load any of these back
   loaded_trace = load("single_trace.iq5")
   loaded_vstep = load("vstep_0.iq5")
   loaded_event = load("event_42.iq5")

.. note::

   When a MetaSegment subtree is saved without its parent TraceFile,
   the loaded MetaSegment's ``.current`` property returns ``None``
   because there is no file-rank ancestor to climb to. Attach it to
   a parent with data to restore ``.current`` access.


Multi-Source Management
-----------------------

A common workflow is comparing raw and filtered versions of the same trace.
After saving and loading, you can store multiple versions of the current
array and switch between them:

.. code-block:: python

   from ionique.storage import save, load
   from ionique.utils import Filter
   import numpy as np

   # Save and reload to get HDF5-backed data
   save(trace, "experiment.iq5")
   trace = load("experiment.iq5")

   # The original data is stored under the "raw" source
   print(trace.current.active_source)       # "raw"
   print(trace.current.available_sources)    # ["raw"]

   # Create a filtered copy and add it as a new source
   filtered = np.copy(trace.current[:])
   filt = Filter(cutoff_frequency=10000, filter_type="lowpass",
                 filter_method="bessel", order=4, bidirectional=True,
                 sampling_frequency=250000)
   filt(filtered)
   trace.add_source("filtered_10kHz", filtered)

   print(trace.current.available_sources)    # ["filtered_10kHz", "raw"]

   # Switch to the filtered source
   trace.switch_source("filtered_10kHz")
   print(trace.current.active_source)        # "filtered_10kHz"

   # All downstream access now reads filtered data
   events = trace.traverse_to_rank("event")
   print(events[0].mean)    # computed from filtered trace

   # Switch back to raw
   trace.switch_source("raw")
   print(events[0].mean)    # computed from raw trace

.. note::

   ``add_source()`` and ``switch_source()`` only work on HDF5-backed
   TraceFiles (i.e., after a save/load cycle or ``to_iq5()``). Calling
   them on an in-memory TraceFile raises ``TypeError``.


Closing File Handles
--------------------

Each LazyArray holds an open HDF5 file handle. When you are done with a
loaded session, close the handles explicitly:

.. code-block:: python

   # Close all handles in a session
   session.close()

   # Or close a single trace's handles
   trace.current.close()

Handles are also released when the LazyArray is garbage collected, but
explicit closing is recommended for long-running scripts or when working
with many files.


Re-saving After Modifications
-----------------------------

You can load an HDF5-backed session, add sources or modify the tree, then
save it again (to the same or a different file):

.. code-block:: python

   from ionique.storage import save, load

   session = load("experiment.iq5")
   trace = session.children[0]

   # Add a filtered source
   trace.add_source("filtered_5kHz", filtered_array)

   # Re-save to a new file (preserves all sources)
   save(session, "experiment_v2.iq5")

The re-saved file contains all sources from the original plus any newly
added ones.


HDF5 File Format
-----------------

Files are standard HDF5, readable by any tool that supports the format
(HDFView, h5py, MATLAB, etc.):

.. code-block:: text

   experiment.iq5
   |
   +-- @format_version = "1.0"
   |
   +-- root/
       +-- @node_type = "TraceFile"
       +-- @rank = "file"
       +-- @start = 0
       +-- @end = 5000000
       +-- @unique_features = '{"sampling_freq": 250000}'
       +-- @active_source = "raw"
       |
       +-- sources/
       |   +-- raw/
       |   |   +-- current  (float32, chunked, gzip)
       |   |   +-- time     (float64, chunked, gzip)
       |   +-- filtered_10kHz/
       |       +-- current  (float32, chunked, gzip)
       |
       +-- children/
           +-- 000_vstep/
           |   +-- @node_type = "MetaSegment"
           |   +-- @rank = "vstep"
           |   +-- @start, @end
           |   +-- children/
           |       +-- 000_event/
           |           +-- @start, @end
           |           +-- @unique_features = '{"baseline": 1.8e-9}'
           +-- 001_vstep/
               ...

Datasets use chunked storage (up to 1M samples per chunk) with gzip
compression level 4 by default. You can customize this:

.. code-block:: python

   # No compression (fastest writes)
   save(trace, "fast.iq5", compression=None, compression_opts=None)

   # Maximum gzip compression (smaller files, slower writes)
   save(trace, "small.iq5", compression="gzip", compression_opts=9)
