#!/usr/bin/env python
"""
Data structure definitions and session file management for analysis.

"""

import datetime
import numpy as np
from ionique.core import MetaSegment, AnySegment, Segment
from ionique.utils import Singleton
# from ionique.setup_log import json_logger
import uuid


# try:
#     import cupy
#     if not cupy.cuda.is_available():
#         raise ImportError
#
#     np = cupy
# except ImportError:
#     import numpy as np

class SessionFileManager(MetaSegment, metaclass=Singleton):
    """
    Singleton-based session manager for hierarchical data.

    This class inherits from ``MetaSegment`` and uses the ``Singleton`` metaclass
    to ensure only one instance exists during a given session. It serves as
    the root segment for a data analysis session and is responsible for managing
    metadata and registered "affectors" (i.e., objects that modify or
    interact with the session).

    Attributes
    ----------
    rank : str
        Fixed rank label ``"root"`` identifying this as the top of the hierarchy.
    affector_table : dict
        Registry mapping UUID strings to metadata entries for each registered
        affector (class name, string representation, and timestamp).
    """
    rank = "root"  # set the rank to "root"

    # @json_logger.log
    def __init__(self) -> None:
        """
        Initialize the session manager.

        Sets the session start time and prepares the affector log structure.
        """
        super().__init__(self, end=2)  # end = 2: Segment end at position 2???
        self.unique_features["SessionStartTime"] = datetime.datetime.now()
        self.affector_table = {}

    # make log management table. contains everything that has happened in this session

    def register_affector(self, affector):
        """
        Register an affector object that influences the session data.

        Records metadata including class name, string representation, and timestamp,
        and logs the event with a unique identifier.

        Parameters
        ----------
        affector : object
            An object that modifies or interacts with the session.

        Returns
        -------
        str
            A UUID string uniquely identifying the registered affector.
        """

        # generate a uuid
        new_uuid = str(uuid.uuid4())
        try:
            affector_repr = repr(affector)
        except Exception:
            affector_repr = "<unrepresentable_repr>"
        entry = {
            "class": affector.__class__.__name__,
            "signature": affector_repr,
            "timestamp": datetime.datetime.now().isoformat()}

        self.affector_table[new_uuid] = entry  # entry here is the entry to log structure(
        #json_logger._log_to_json({
        #     "action": "register_affector",
        #     "uuid": new_uuid,
        #     "entry": entry
        # })
        return new_uuid


    def add_child(self, child: AnySegment) -> None:
        """
        Add a single child segment to the session's hierarchy.

        Parameters
        ----------
        child : AnySegment
            The segment to be added as a child.
        """
        self.children.append(child)

    def add_children(self, children: list[AnySegment]) -> None:
        """
        Add multiple child segments to the session.

        Parameters
        ----------
        children : list of AnySegment
            A list of segments to be added as children.
        """
        self.children.extend(children)

    def _set_children_nocheck(self, children: list[AnySegment]) -> None:
        """
        Replace all existing children with new ones without validation.

        Parameters
        ----------
        children : list of AnySegment
            A list of new segments to set as children.
        """
        self.children.clear()
        self.children = children

    def _remove(self, child):
        """
        Remove a specific child segment from the session.

        Parameters
        ----------
        child : AnySegment
            The child segment to be removed.
        """
        if child in self.children:
            self.children.remove(child)

    def close(self):
        """Close any open HDF5 file handles held by child TraceFiles."""
        from ionique.storage import LazyArray
        for child in self.children:
            if hasattr(child, "current") and isinstance(child.current, LazyArray):
                child.current.close()
            if hasattr(child, "time") and isinstance(child.time, LazyArray):
                child.time.close()
            if hasattr(child, "close") and child is not self:
                child.close()


class TraceFile(Segment):
    """
    Data structure for representing a single trace file with current and optional voltage information.

    This class inherits from ``Segment`` and encapsulates current and voltage data. It sets up
    segment metadata, defines parent-child hierarchy, and optionally initializes child segments
    based on voltage steps. If voltage steps are provided, corresponding child segments of rank
    ``"vstep"`` are created automatically.

    Parameters
    ----------
    current : numpy.ndarray
        Array of ionic current values.
    voltage : list of tuple or None, optional
        List of ``((start, end), voltage_value)`` tuples used to create child segments
        for each voltage step. Defaults to None.
    rank : str, optional
        Segment rank label. Defaults to ``"file"``.
    parent : Segment or None, optional
        Parent segment to which this trace belongs. Defaults to None.
    unique_features : dict, optional
        Dictionary of metadata such as sampling frequency. Defaults to an empty dict.
    metadata : dict, optional
        Additional metadata. Defaults to an empty dict.
    """

    # @json_logger.log
    def __init__(self, current: np.ndarray, voltage=None, rank="file", parent=None,
                 unique_features: dict = {}, metadata: dict = {}):
        """
        Initialize the TraceFile and optionally create voltage-step child segments.
        """
        super().__init__(current)
        self.rank = "file"
        self.parent = parent
        self.unique_features = unique_features
        self.voltage = voltage
        self.start = 0
        self.end = len(self.current)
        self.metadata = metadata
        self.uuid = None
        self.sampling_freq = self.unique_features.get("sampling_freq")
        self.time = np.arange(self.start, self.end) / self.sampling_freq

        # If voltage data exists, create MetaSegment instance for each voltage step
        if self.voltage is not None:
            self.add_children([MetaSegment(start, end, parent=self, rank="vstep",
                                           unique_features={"voltage": v})
                               for (start, end), v in voltage])
        if self.parent is not None:
            self.parent.add_child(self)

    def plot(self, rank, axes, downsample_per_rank, color_per_rank):
        """
        Plot the trace data at a specified rank with per-rank styling options.

        Parameters
        ----------
        rank : str
            The segment rank at which to render the plot.
        axes : object
            The axes or figure object to draw on.
        downsample_per_rank : dict
            Mapping of rank label to downsampling factor for rendering.
        color_per_rank : dict
            Mapping of rank label to color specification for rendering.

        Notes
        -----
        Not yet implemented.
        """
        pass

    def add_source(self, name, current_array):
        """Add a new named source (e.g. a filtered version) to the HDF5 backing store.

        Only works when ``self.current`` is a :class:`~ionique.storage.LazyArray`
        (i.e. after a save/load cycle).

        Parameters
        ----------
        name : str
            Source name (e.g. ``"filtered_10kHz"``).
        current_array : numpy.ndarray
            The filtered current array. Must have the same length as the
            existing current.
        """
        from ionique.storage import LazyArray
        if not isinstance(self.current, LazyArray):
            raise TypeError(
                "add_source() requires an HDF5-backed TraceFile "
                "(save then load first)."
            )
        import h5py as _h5py
        la = self.current
        la.close()
        with _h5py.File(la._filepath, "a") as f:
            src_grp = f[la._sources_group_path]
            if name in src_grp:
                del src_grp[name]
            new_grp = src_grp.create_group(name)
            arr = np.asarray(current_array)
            chunk = min(len(arr), 1_000_000) if len(arr) > 0 else None
            new_grp.create_dataset(
                "current", data=arr,
                chunks=(chunk,) if chunk else None,
                compression="gzip", compression_opts=4,
            )

    def switch_source(self, name):
        """Switch which stored version ``.current`` reads from.

        All descendant ``MetaSegment`` nodes automatically use the new source
        because they resolve ``.current`` by climbing to this ``TraceFile``.

        Parameters
        ----------
        name : str
            Source name to activate (e.g. ``"raw"`` or ``"filtered_10kHz"``).
        """
        from ionique.storage import LazyArray
        if not isinstance(self.current, LazyArray):
            raise TypeError(
                "switch_source() requires an HDF5-backed TraceFile "
                "(save then load first)."
            )
        self.current.switch_source(name)

    def delete(self):
        """
        Delete the current object, removing it from its parent

        """
        try:
            if self.parent is not None:
                self.parent._remove(self)
        except Exception as error:
            print(error)
        super().delete()


# class RoiSegment(MetaSegment):
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.keys=kwargs.keys()
#         if hasattr(self,'parent'):
#             if hasattr(self.parent,'sampling_freq'):
#                 self.sampling_freq=self.parent.sampling_freq

#     def get_bounds(self,seconds=True):
#         if seconds and isinstance(self.start,int):
#             return(self.start/self.sampling_freq,self.end/self.sampling_freq)
#         if (seconds and isinstance(self.start,float)) or
#             (not seconds and isinstance(self.start,int)):
#             return(self.start,self.end)
#         if not seconds and isinstance(self.start,float):
#             return(int(self.start*self.sampling_freq),int(self.end*self.sampling_freq))
