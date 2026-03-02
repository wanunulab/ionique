#!/usr/bin/env python
"""
HDF5-backed persistent storage for ionique segment trees.

Provides ``save()`` and ``load()`` functions that serialize any segment tree
(SessionFileManager, TraceFile, Segment, MetaSegment, or arbitrary subtrees)
to a single ``.iq5`` file and reconstruct it with lazy, disk-backed
array access via ``LazyArray``.

The ``.iq5`` format also supports **purge-to-disk** (``to_iq5()``) and
**incremental sync** (``sync_iq5()``) workflows, where the file acts as a
live backing store rather than a snapshot.
"""

import json
import numpy as np

try:
    import h5py
except ImportError as exc:
    raise ImportError(
        "h5py is required for ionique.storage. Install it with: pip install h5py"
    ) from exc

from ionique.core import MetaSegment, Segment

# Avoid circular import at module level — these are only needed inside
# load() / save() and are imported lazily there or referenced by string.
_FORMAT_VERSION = "1.0"
IQ5_EXTENSION = ".iq5"


# ---------------------------------------------------------------------------
# LazyArray
# ---------------------------------------------------------------------------

class LazyArray:
    """Wraps an HDF5 dataset path so slicing reads only the requested chunk.

    Parameters
    ----------
    filepath : str
        Path to the HDF5 file on disk.
    sources_group_path : str
        HDF5 path to the ``sources/`` group (e.g. ``"root/sources"``).
    dataset_name : str
        Dataset name inside a source group (e.g. ``"current"``).
    active_source : str
        Initial source name (e.g. ``"raw"``).
    """

    def __init__(self, filepath, sources_group_path, dataset_name, active_source="raw"):
        self._filepath = filepath
        self._sources_group_path = sources_group_path
        self._dataset_name = dataset_name
        self._active_source = active_source
        self._file = None  # opened lazily

    # -- lazy open / close --------------------------------------------------

    def _open(self):
        if self._file is None or not self._file.id.valid:
            self._file = h5py.File(self._filepath, "r")

    def _open_rw(self):
        """Re-open in append mode for writes."""
        self.close()
        self._file = h5py.File(self._filepath, "a")

    @property
    def _dataset(self):
        self._open()
        return self._file[f"{self._sources_group_path}/{self._active_source}/{self._dataset_name}"]

    def close(self):
        if self._file is not None and self._file.id.valid:
            self._file.close()
            self._file = None

    # -- source switching ---------------------------------------------------

    @property
    def active_source(self):
        return self._active_source

    def switch_source(self, name):
        """Switch which ``sources/<name>/`` this array reads from."""
        # Validate the source exists
        self._open()
        path = f"{self._sources_group_path}/{name}/{self._dataset_name}"
        if path not in self._file:
            available = list(self._file[self._sources_group_path].keys())
            raise KeyError(
                f"Source '{name}' does not contain '{self._dataset_name}'. "
                f"Available sources: {available}"
            )
        self._active_source = name

    @property
    def available_sources(self):
        self._open()
        return list(self._file[self._sources_group_path].keys())

    # -- numpy-array-like interface -----------------------------------------

    def __getitem__(self, key):
        return self._dataset[key]

    def __setitem__(self, key, value):
        self._open_rw()
        ds = self._file[f"{self._sources_group_path}/{self._active_source}/{self._dataset_name}"]
        ds[key] = value
        self._file.flush()
        # Re-open read-only
        self.close()
        self._open()

    def __len__(self):
        return self._dataset.shape[0]

    @property
    def shape(self):
        return self._dataset.shape

    @property
    def dtype(self):
        return self._dataset.dtype

    @property
    def ndim(self):
        return self._dataset.ndim

    @property
    def size(self):
        return self._dataset.size

    def __array__(self, dtype=None, copy=None):
        arr = self._dataset[:]
        if dtype is not None:
            arr = arr.astype(dtype)
        return arr

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        """Intercept numpy ufuncs so ``np.mean(lazy)`` etc. work."""
        converted = []
        for inp in inputs:
            if isinstance(inp, LazyArray):
                converted.append(np.asarray(inp))
            else:
                converted.append(inp)
        return getattr(ufunc, method)(*converted, **kwargs)

    def __repr__(self):
        return (
            f"LazyArray(file={self._filepath!r}, "
            f"source={self._active_source!r}, "
            f"dataset={self._dataset_name!r}, "
            f"shape={self.shape})"
        )


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------

def save(seg, filepath, compression="gzip", compression_opts=4):
    """Save any segment (and its entire subtree) to an HDF5 file.

    Parameters
    ----------
    seg : AnySegment
        The root of the subtree to save.
    filepath : str
        Destination ``.iq5`` file path.
    compression : str
        HDF5 compression filter name.
    compression_opts : int
        Compression level.
    """
    with h5py.File(filepath, "w") as f:
        f.attrs["format_version"] = _FORMAT_VERSION
        root_grp = f.create_group("root")
        _save_node(root_grp, seg, compression, compression_opts)


def _save_node(grp, seg, compression, compression_opts):
    """Recursively save a single node and its children."""
    from ionique.datatypes import TraceFile, SessionFileManager

    # -- node type ----------------------------------------------------------
    grp.attrs["node_type"] = type(seg).__name__

    # -- positional attrs ---------------------------------------------------
    if seg.rank is not None:
        grp.attrs["rank"] = seg.rank
    if seg.start is not None:
        grp.attrs["start"] = int(seg.start)
    if seg.end is not None:
        grp.attrs["end"] = int(seg.end)

    # -- unique_features: split scalars vs arrays ---------------------------
    scalar_features = {}
    for key, val in seg.unique_features.items():
        if isinstance(val, np.ndarray):
            _write_dataset(grp, key, val, compression, compression_opts)
        else:
            scalar_features[key] = _make_json_safe(val)

    grp.attrs["unique_features"] = json.dumps(scalar_features)

    # -- extra_attrs (class-specific) ---------------------------------------
    extra = {}
    if isinstance(seg, TraceFile):
        if hasattr(seg, "metadata") and seg.metadata:
            extra["metadata"] = _make_json_safe(seg.metadata)
        if hasattr(seg, "uuid") and seg.uuid is not None:
            extra["uuid"] = str(seg.uuid)
        if hasattr(seg, "sampling_freq") and seg.sampling_freq is not None:
            extra["sampling_freq"] = float(seg.sampling_freq)
    elif isinstance(seg, SessionFileManager):
        if hasattr(seg, "affector_table"):
            extra["affector_table"] = seg.affector_table

    if extra:
        grp.attrs["extra_attrs"] = json.dumps(extra)

    # -- sources (array data) -----------------------------------------------
    _has_current = hasattr(seg, "current") and not isinstance(seg, MetaSegment)
    if _has_current and seg.current is not None:
        sources_grp = grp.create_group("sources")

        if isinstance(seg.current, LazyArray):
            # Copy all sources from the original HDF5
            la = seg.current
            la._open()
            src_hdf = la._file[la._sources_group_path]
            for src_name in src_hdf:
                src_hdf.copy(src_hdf[src_name], sources_grp, name=src_name)
            grp.attrs["active_source"] = la.active_source
        else:
            # Plain numpy array → write as "raw"
            raw_grp = sources_grp.create_group("raw")
            _write_dataset(raw_grp, "current", np.asarray(seg.current),
                           compression, compression_opts)

            if hasattr(seg, "time") and seg.time is not None:
                time_arr = np.asarray(seg.time)
                _write_dataset(raw_grp, "time", time_arr,
                               compression, compression_opts)

            grp.attrs["active_source"] = "raw"

        # voltage — store as array or JSON tuples
        if isinstance(seg, TraceFile) and hasattr(seg, "voltage") and seg.voltage is not None:
            grp.attrs["voltage_steps"] = json.dumps(
                [[[int(s), int(e)], float(v)] for (s, e), v in seg.voltage]
            )

    # -- children -----------------------------------------------------------
    if seg.children:
        children_grp = grp.create_group("children")
        for idx, child in enumerate(seg.children):
            child_rank = child.rank or "unknown"
            child_name = f"{idx:03d}_{child_rank}"
            child_grp = children_grp.create_group(child_name)
            _save_node(child_grp, child, compression, compression_opts)


def _write_dataset(grp, name, arr, compression, compression_opts):
    """Write a numpy array as a chunked, compressed HDF5 dataset."""
    if arr.ndim == 0:
        grp.create_dataset(name, data=arr)
        return
    chunk_size = min(len(arr), 1_000_000) if len(arr) > 0 else None
    chunks = (chunk_size,) + arr.shape[1:] if chunk_size else None
    grp.create_dataset(
        name, data=arr, chunks=chunks,
        compression=compression, compression_opts=compression_opts,
    )


def _make_json_safe(obj):
    """Convert an object to a JSON-serializable form."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    # datetime → isoformat string
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


# ---------------------------------------------------------------------------
# Node-path walking and assignment
# ---------------------------------------------------------------------------

def _walk_node_paths(seg, prefix="root"):
    """Yield ``(node, hdf5_group_path)`` pairs matching the save layout."""
    yield seg, prefix
    for idx, child in enumerate(seg.children):
        child_rank = child.rank or "unknown"
        child_path = f"{prefix}/children/{idx:03d}_{child_rank}"
        yield from _walk_node_paths(child, child_path)


def _assign_grp_paths(seg, filepath, prefix="root"):
    """Set ``_iq5_grp_path``, ``_iq5_path``, and ``_iq5_stale_paths`` on every node."""
    for node, grp_path in _walk_node_paths(seg, prefix):
        node._iq5_grp_path = grp_path
        node._iq5_path = filepath
        if not hasattr(node, '_iq5_stale_paths'):
            node._iq5_stale_paths = []


# ---------------------------------------------------------------------------
# Incremental sync
# ---------------------------------------------------------------------------

def _close_lazy_handles(seg):
    """Close all open LazyArray file handles in the tree."""
    for node, _ in _walk_node_paths(seg):
        if isinstance(node, MetaSegment):
            continue  # current/time are properties that delegate to parent
        for attr in ('current', 'time'):
            val = getattr(node, attr, None)
            if isinstance(val, LazyArray):
                val.close()


def _sync_to_file(seg, filepath, compression="gzip", compression_opts=4):
    """Write new/changed nodes to *filepath* incrementally."""
    # Close read-only handles so we can open in append mode
    _close_lazy_handles(seg)
    with h5py.File(filepath, "a") as f:
        _sync_node(f, seg, "root", filepath, compression, compression_opts)


def _sync_node(f, seg, grp_path, filepath, compression, compression_opts):
    """Recursively sync a single node: delete stale children, write new ones."""
    # 1. Delete stale children paths
    for stale_path in getattr(seg, '_iq5_stale_paths', []):
        if stale_path in f:
            del f[stale_path]
    seg._iq5_stale_paths = []

    # 2. Update mutable attrs if this node already exists
    if grp_path in f:
        _update_node_attrs(f[grp_path], seg)

    # 3. Walk children — write new ones, recurse into existing ones
    children_path = f"{grp_path}/children"

    for idx, child in enumerate(seg.children):
        child_rank = child.rank or "unknown"
        child_name = f"{idx:03d}_{child_rank}"
        child_grp_path = f"{children_path}/{child_name}"

        if getattr(child, '_iq5_grp_path', None) is None:
            # NEW node — create group, save fully
            if children_path not in f:
                f.create_group(children_path)
            child_grp = f.create_group(child_grp_path)
            _save_node(child_grp, child, compression, compression_opts)
            # Assign paths to the new node and all its descendants
            _assign_grp_paths(child, filepath, child_grp_path)
        else:
            # EXISTING node — recurse to check its children
            _sync_node(f, child, child_grp_path, filepath, compression, compression_opts)


def _update_node_attrs(grp, seg):
    """Update ``unique_features`` for an existing HDF5 group."""
    scalar_features = {}
    for key, val in seg.unique_features.items():
        if not isinstance(val, np.ndarray):
            scalar_features[key] = _make_json_safe(val)
    grp.attrs["unique_features"] = json.dumps(scalar_features)


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

def load(filepath, parent=None):
    """Load a segment tree from an HDF5 file.

    Parameters
    ----------
    filepath : str
        Path to an ``.iq5`` file.
    parent : AnySegment or None
        Optional parent to attach the loaded root to.

    Returns
    -------
    AnySegment
        The reconstructed root node with ``LazyArray``-backed data.
    """
    with h5py.File(filepath, "r") as f:
        root_grp = f["root"]
        node = _load_node(filepath, root_grp, parent)
    return node


def _load_node(filepath, grp, parent):
    """Recursively reconstruct a single node and its children."""
    from ionique.datatypes import TraceFile, SessionFileManager

    node_type = grp.attrs["node_type"]
    rank = grp.attrs.get("rank", None)
    start = int(grp.attrs["start"]) if "start" in grp.attrs else None
    end = int(grp.attrs["end"]) if "end" in grp.attrs else None

    # -- unique_features ----------------------------------------------------
    uf_json = grp.attrs.get("unique_features", "{}")
    unique_features = json.loads(uf_json)

    # Array-valued unique_features stored as datasets on the group
    for key in grp:
        if key not in ("sources", "children"):
            item = grp[key]
            if isinstance(item, h5py.Dataset):
                unique_features[key] = item[:]

    # -- extra_attrs --------------------------------------------------------
    extra_json = grp.attrs.get("extra_attrs", "{}")
    extra = json.loads(extra_json)

    # -- sources ------------------------------------------------------------
    has_sources = "sources" in grp
    active_source = grp.attrs.get("active_source", "raw")
    sources_path = f"{grp.name}/sources"

    # -- reconstruct node ---------------------------------------------------
    if node_type == "TraceFile":
        node = TraceFile.__new__(TraceFile)
        # Initialize base attributes
        Segment.__init__.__wrapped__ if hasattr(Segment.__init__, '__wrapped__') else None
        node.parent = parent
        node.children = []
        node.start = start
        node.end = end
        node.rank = rank or "file"
        node.unique_features = unique_features
        node.metadata = extra.get("metadata", {})
        node.uuid = extra.get("uuid", None)
        node.sampling_freq = extra.get("sampling_freq",
                                        unique_features.get("sampling_freq"))

        if has_sources:
            node.current = LazyArray(filepath, sources_path, "current", active_source)
            # Check if time dataset exists
            with h5py.File(filepath, "r") as f:
                time_path = f"{sources_path}/raw/time"
                has_time = time_path in f
            if has_time:
                node.time = LazyArray(filepath, sources_path, "time", "raw")
            else:
                # Reconstruct time from sampling_freq
                if node.sampling_freq:
                    node.time = np.arange(start, end) / node.sampling_freq
                else:
                    node.time = None
        else:
            node.current = None
            node.time = None

        # Restore voltage
        if "voltage_steps" in grp.attrs:
            node.voltage = [
                ((int(s), int(e)), float(v))
                for [s, e], v in json.loads(grp.attrs["voltage_steps"])
            ]
        else:
            node.voltage = None

    elif node_type == "Segment":
        node = Segment.__new__(Segment)
        node.parent = parent
        node.children = []
        node.start = start
        node.end = end
        node.rank = rank
        node.unique_features = unique_features

        if has_sources:
            node.current = LazyArray(filepath, sources_path, "current", active_source)
        else:
            node.current = None

    elif node_type == "SessionFileManager":
        node = SessionFileManager.__new__(SessionFileManager)
        node.parent = parent
        node.children = []
        node.start = start
        node.end = end
        node.rank = rank or "root"
        node.unique_features = unique_features
        node.affector_table = extra.get("affector_table", {})

    else:
        # MetaSegment or unknown — treat as MetaSegment
        node = MetaSegment(start=start or 0, end=end or 0,
                           parent=parent, rank=rank,
                           unique_features=unique_features)

    # -- iq5 tracking -------------------------------------------------------
    # Strip leading "/" from HDF5 absolute path to match _walk_node_paths
    grp_path = grp.name.lstrip("/")
    node._iq5_grp_path = grp_path
    node._iq5_path = filepath
    node._iq5_stale_paths = []

    # -- children -----------------------------------------------------------
    if "children" in grp:
        children_grp = grp["children"]
        child_names = sorted(children_grp.keys())
        for cname in child_names:
            child_node = _load_node(filepath, children_grp[cname], parent=node)
            node.children.append(child_node)

    return node
