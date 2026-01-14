#!/usr/bin/env python
"""
    adaptation from "core.py" by Jacob Scheriber
    https://github.com/jmschrei/PyPore
This holds the core data types which may be abstracted in
many different applications.
This module defines a tree-based framework for representing, parsing, and annotating
segments of ionic current data.
"""


import re
import json
from contextlib import contextmanager
from itertools import chain
# from typing import Type, TypeVar
from typing import TypeVar
from functools import cached_property
import numpy as np


AnySegment = TypeVar("AnySegment", bound="AbstractSegmentTree")


class AbstractSegmentTree(object):
    """
    Class for managing hierarchical segments.

    This class supports a tree structure where each segment can contain multiple
    child segments, enabling recursive parsing and analysis of nested data.
    It provides utilities to manage relationships between segments, apply parsers,
    and extract subsegments by rank.
    """
    # Memory optimization by limiting attributes
    __slots__ = ('parent', 'children', 'start', 'end', 'rank', '__dict__')

    def __init__(self) -> None:
        """
        Initialize the segment
        """
        # TODO: check if unique_features should be added:
        self.unique_features = {}
        self.parent: AnySegment | None = None
        self.children: list[AnySegment] = []

        # # self._slice_relative: Type(np.s_)= np.s_[::]
        self.start: int | None = 0
        self.end: int | None = None
        self.rank: str = None
        pass

    def parse(self, parser, newrank: str, at_child_rank: str | None = None, **kwargs) -> bool:
        """
        Parses the data in the segment or at a particular rank of child segments
        into children segments with a new rank.

        :param parser: A parser object with a `parse` method and required input attributes.
        :type parser: Parser
        :param newrank: Rank to assign to the newly created child segments.
        :type newrank: str
        :param at_child_rank: Determines whether to traverse the children tree down to a given rank.
        :type at_child_rank: str or None
        :param kwargs: Additional arguments to pass to the parser.
        :return: True if parsing was successful, otherwise raises an exception.
        :rtype: bool
        """
        try:
            # TODO: get the features from parsers (test)
            required_parent_attributes = parser.get_required_parent_attributes()

            def _parse_one(target: AnySegment) -> None:
                """
                Called if at_child_rank_ is passed to "parse" method
                """
                attributes = {}
                for attr_name in required_parent_attributes:
                    attributes[attr_name] = target.get_feature(attr_name)
                    
                # if "sampling_freq" in required_parent_attributes:
                #     attributes["sampling_freq"]=\
                #        self.climb_to_rank('file').unique_features["sampling_freq"]
                parser_results = parser.parse(**attributes, **kwargs)


                # print(f"parent start={target.start}, end={target.end}")

                children = [MetaSegment(int(start)+target.start, int(end)+target.start, parent=target,
                                        rank=newrank, unique_features=unique_features)
                                        for start, end, unique_features in parser_results]
                target.clear_children()
                target.add_children(children)

            if at_child_rank is None or at_child_rank == self.rank:
                _parse_one(self)
            else:
                targets = self.traverse_to_rank(at_child_rank)
                for target in targets:
                    _parse_one(target)
        except Exception as error:
            raise error

        return True

    def get_feature(self, name: str):
        """
        Gets the 'name' feature of the current segment or its parent
        """
        if name in self.unique_features.keys():
            return self.unique_features[name]
        elif hasattr(self, name):
            return getattr(self, name)
        elif self.parent is not None:
            return self.parent.get_feature(name)
        else:
            return None

    @cached_property
    def relative_start(self) -> int:
        """
        Get the start position relative to parent segment
        :return: start position
        """
        if self.parent is not None:
            return self.start - self.parent.start
        return self.start

    @cached_property
    def relative_end(self) -> int:
        """
        Get end position relative to parent segment
        :return: end position
        """
        if self.parent is not None:
            return self.end - self.parent.start
        return self.end

    # TODO: When data is avilable, check the output types and fix typing

    @cached_property
    def slice(self) -> np.ndarray:
        """
        Slice the array to get the data between start-end segment
        :return: sliced np array
        """
        return np.s_[self.start:self.end]

    @cached_property
    def relative_slice(self) -> np.ndarray:
        """
        Slice the array to get the data between end-start segment
        :return: sliced np array
        """
        return np.s_[self.relative_start:self.relative_end]

    @cached_property
    def n(self) -> int:
        """
        Get the length of the segment
        :return: len(segment)
        """
        return self.end-self.start

    def get_top_parent(self) -> AnySegment:
        """
        Recursively go up and find top most parent
        :return: parent
        """
        if self.parent is not None:
            return self.parent.get_top_parent(self)
        return self

    def climb_to_rank(self, rank: str) -> AnySegment | None:
        """
        Go up and find the segment with the specified rank
        :return: segment
        """
        if self.rank == rank:
            return self
        # elif self.parent != None:
        elif self.parent is not None:
            return self.parent.climb_to_rank(rank)
        else:
            return None

    def add_child(self, child: AnySegment) -> None:
        """
        Add a single child
        """
        self.add_children([child])

    def add_children(self, children: list[AnySegment]) -> None:
        """
        Add multiple children if:
        1. Child position is the within parent's segment.
        2. The length of the child's segment is > 0
        3. There is no overlap between consecutive children

        Or add children with no check
        """
        if self.start is not None and self.end is not None:

            assert all([self.start <= child.start < child.end <= self.end for child in children]), \
                f"Children's positions are outside the parent's range ({self.start}, {self.end})."
        else:

            assert all([child.n > 0 for child in children]), "Children segment length <= 0."

        # # Sort the list of children
        temp_children = sorted(self.children + children, key=lambda x: (x.start, x.end))

        assert all([child0.end <= child1.start for child0, child1 in
                    zip(temp_children[:-1], temp_children[1:])]), \
            "Children segments overlap with consecutive segments."

        self._set_children_nocheck(temp_children)

    def _set_children_nocheck(self, children: list[AnySegment]) -> None:
        """
        Called in add_children method to add children with no check
        """
        self.children = children

    def clear_children(self):
        """
        Clear the list of children
        """
        self.children.clear()
        return

    def traverse_to_rank(self, rank: str) -> list:
        """
        Traverse the tree rank and get the list of the segments of the rank
        :param: rank
        :return: list of segments
        """
        if self.rank == rank:
            return [self]
        else:
            if not self.children:
                return []
            else:
                return list(chain(*[child.traverse_to_rank(rank) for child in self.children]))

    def summary(self):
        """
        Provide a summary of existing ranks and number of elements at each rank
        :return: dict of (rank: count) in root→children order
        """
        ranks_in_order = []
        seen = set()

        def collect(seg):
            if seg.rank not in seen:
                seen.add(seg.rank)
                ranks_in_order.append(seg.rank)
            
            for child in seg.children:
                collect(child)

        collect(self)
        return {rank: len(self.traverse_to_rank(rank)) for rank in ranks_in_order}
    
# class ParsableMixin:
#     def parse(self,parser,newrank:str,**kwargs)->bool:
#         required_parent_attributes=parser.get_required_parent_attributes()
#         attributes=dict([(attr_name, getattr(self,attr_name,None))
#                          for attr_name in required_parent_attributes])
#         self.clear_children()
#         parser_results=parser.parse(**attributes,**kwargs)
#         children = [MetaSegment(start,end,parent=self,rank=newrank,
#                                 unique_features=unique_features)
#                     for start,end,unique_features in parser_results]
#         self.add_children(children)


class MetaSegment(AbstractSegmentTree):
    """
    The metadata on an abstract segment of ionic current. All information about a segment can be
    loaded, without the expectation of the array of floats.
    """
    # Limit attributes to "unique_features"
    __slots__ = "unique_features"

    def __init__(self, start: int, end: int,
                 parent: AnySegment | None = None, rank: str | None = None,
                 unique_features: dict | None = {}, **kwargs):
        """
        :param start: Start index of the segment.
        :type start: int
        :param end: End index of the segment.
        :type end: int
        :param parent: Parent segment in the tree (optional).
        :type parent: AbstractSegmentTree or None
        :param rank: Rank identifier for this segment (optional).
        :type rank: str or None
        :param unique_features: Dictionary of metadata features.
        :type unique_features: dict
        """
        super().__init__()
        # pointers to lower level segments (sub-segments)
        # self.slice=np.s_[::]
        # self.slice_relative=np.s_[::]
        self.start = start
        self.end = end
        self.parent = parent
        self.unique_features = unique_features
        self.rank = rank
        # for key, value in kwargs.items():
        #     setattr(self, key, value)
        # If current is passed in, get metadata directly from it, then remove
        # # the reference to that array.
        # if hasattr(self, "current"):
        #     self.n = len(self.current)
        #     self.mean = np.mean(self.current)
        #     self.std = np.std(self.current)
        #     self.min = np.min(self.current)
        #     self.max = np.max(self.current)
        #     del self.current

        # Fill in start, end, and duration given that you only have two of them.
        # if hasattr(self, "start") and hasattr(self, "end") and not hasattr(self, "duration"):
        #     self.duration = self.end - self.start
        # elif hasattr(self, "start") and hasattr(self, "duration") and not hasattr(self, "end"):
        #     self.end = self.start + self.duration
        # elif hasattr(self, "end") and hasattr(self, "duration") and not hasattr(self, "start"):
        #     self.start = self.end - self.duration
    @property
    def current(self):
        """
        Get the current data of the segment if the segment correlates to the file
        :return: current
        """
        try:
            cur = self.climb_to_rank('file').current[self.start:self.end]
            return cur
        except:
            return None

    #########################################################
    # The next four methods compute the basic statistics    #
    #  of the current with the segment                      #
    #########################################################
    @property
    def mean(self):
        """
        Calculate the mean of the current array.

        :return: Mean value of the current array.
        :rtype: float
        """
        return np.mean(self.current)

    @property
    def std(self):
        """
        Calculate the standard deviation of the current array.

        :return: Standard deviation of the current array.
        :rtype: float
        """
        return np.std(self.current)

    @property
    def min(self):
        """
        Calculate the minimum value of the current array.

        :return: Minimum value of the current array.
        :rtype: float
        """
        return np.min(self.current)

    @property
    def max(self):
        """
        Calculate the maximum value of the current array.

        :return: Maximum value of the current array.
        :rtype: float
        """
        return np.max(self.current)

    @property
    def time(self):
        """
        Get the time data of the segment if the corresponding rank is in file
        :return: time
        """
        return self.climb_to_rank("file").time[self.start:self.end]

    @property
    def duration(self) -> float:
        """
        Get the duration of the segment = start - end
        :return: duration
        """
        return self.time[-1]-self.time[0]

    def __repr__(self) -> str:
        """
        The representation is a JSON.
        :return: string representation of JSON
        """
        return self.to_json()

    def __len__(self):
        """
        The length of the metasegment is the length of the ionic current it
        is representing.
        """
        return self.n

    def delete(self):
        """
        Delete itself. There are no arrays with which to delete references for.
        """

        del self

    def to_meta(self):
        """
        Kept to allow for error handling, but since it's already a metasegment
        it won't actually do anything.
        """
        pass

    def to_dict(self):
        """
        Return a dict representation of the metadata, usually used prior to
        converting the dict to a JSON.
        """
        # if hasattr(self, 'keys'):
        #     keys = self.keys
        # else:
        #     keys = ['mean', 'std', 'min', 'max', 'start', 'end', 'duration']
        # dict_meta = {i: getattr(self, i) for i in keys if hasattr(self, i)}
        # dict_meta['name'] = self.__class__.__name__
        # return dict_meta
        if hasattr(self, 'keys'):
            keys = self.keys
        else:
            keys = ['mean', 'std', 'min', 'max', 'start', 'end', 'duration']
        dict_meta = {i: self._convert_if_numpy(getattr(self, i)) for i in keys if hasattr(self, i)}
        dict_meta['name'] = self.__class__.__name__
        return dict_meta

    def _convert_if_numpy(self, obj):
        """
        Convert numpy data types to native Python types.
        """
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        return obj

    def to_json(self, filename=None):
        """
        Return a JSON representation of this, by reporting the important
        metadata.
        """

        # _json = json.dumps(self.to_dict(), indent=4, separators=(',', ' : '))
        # if filename:
        #     with open(filename, 'w') as outfile:
        #         outfile.write(_json)
        # return _json
        if filename:
            _json = json.dumps(self.to_dict(), indent=4, separators=(',', ' : '))
            return _json
        _json = json.dumps(self.to_dict(), indent=4, separators=(',', ' : '))
        return _json

    @classmethod
    def from_json(self, filename=None, in_json=None):
        """
        Read in a metasegment from a JSON and return a metasegment object.
        Either pass in a file which has a segment stored, or an actual JSON
        object.
        """

        assert filename or in_json and not (filename and in_json)

        if filename:
            with open(filename, 'r') as infile:
                in_json = ''.join([line for line in infile])

        words = re.findall(r"\[[\w'.-]+\]|[\w'.-]+", in_json)
        attrs = {words[i]: words[i+1] for i in range(0, len(words), 2)}

        return MetaSegment(**attrs)


class Segment(AbstractSegmentTree):
    """
    A segment of ionic current, and methods relevant for collecting metadata. The ionic current is
    expected to be passed as a numpy array of floats. Metadata methods (mean, std..) are decorated
    as properties to reduce overall computational time, making them calculated on the fly rather
    than during analysis.
    """

    def __init__(self, current, **kwargs):
        """
        The segment must have a list of ionic current, of which it stores some statistics about.
        It may also take in as many keyword arguments as needed, such as start time or duration
        if already known. Cannot override statistical measurements.
        :param current: Numpy array of current data points.
        :type current: np.ndarray
        :param kwargs: Additional attributes like 'start', 'end', 'rank', etc.
        """

        super().__init__()
        self.current = current
        for key, value in kwargs.items():
            with ignored(AttributeError):
                setattr(self, key, value)

    def __repr__(self):
        """
        The string representation of this object is the JSON.
        """
        return self.to_json()

    def __len__(self):
        """
        The length of a segment is the length of the underlying ionic current
        array.
        """

        return self.n

    def to_dict(self):
        """
        Return a dict representation of the metadata, usually used prior to
        converting the dict to a JSON.
        """
        # if hasattr(self, 'keys'):
        #     keys = self.keys
        # else:
        #     keys = ['mean', 'std', 'min', 'max', 'start', 'end', 'duration']
        # d = {i: getattr(self, i) for i in keys if hasattr(self, i)}
        # d['name'] = self.__class__.__name__
        # return d
        if hasattr(self, 'keys'):
            keys = self.keys
        else:
            keys = ['mean', 'std', 'min', 'max', 'start', 'end', 'duration']
        dict_meta = {i: self._convert_if_numpy(getattr(self, i)) for i in keys if hasattr(self, i)}
        dict_meta['name'] = self.__class__.__name__
        return dict_meta

    def _convert_if_numpy(self, obj):
        """
        Convert numpy data types to regular Python type.
        """
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        return obj

    def to_json(self, filename=None):
        ## TODO: change this function caausing the error!
        """
        Return a JSON representation of this, by reporting the important
        metadata.
        """
        #
        # _json = json.dumps(self.to_dict(), indent=4, separators=(',', ' : '))
        # if filename:
        #     with open(filename, 'w') as outfile:
        #         outfile.write(_json)
        # return _json
        if filename:
            _json = json.dumps(self.to_dict(), indent=4, separators=(',', ' : '))
            return _json
        _json = json.dumps(self.to_dict(), indent=4, separators=(',', ' : '))
        return _json

    def to_meta(self):
        """
        Convert from a segment to a 'metasegment', which stores only metadata
        about the segment and not the full array of ionic current.
        """

        for key in ['mean', 'std', 'min', 'max', 'end', 'start', 'duration']:
            with ignored(KeyError, AttributeError):
                self.__dict__[key] = getattr(self, key)
        del self.current

        self.__class__ = type("MetaSegment", (MetaSegment, ), self.__dict__)

    def delete(self):
        """
        Deleting this segment requires deleting its reference to the ionic
        current array, and then deleting itself.
        """

        with ignored(AttributeError):
            del self.current

        del self

    def scale(self, sampling_freq):
        """
        Rescale all of the values to go from samples to seconds.
        """

        # Changed the code here for the test units:
        # When set to None error occurs

        # with ignored(AttributeError):
        #     self.start /= sampling_freq
        #     self.end /= sampling_freq
        #     self.duration /= sampling_freq
        with ignored(AttributeError):
            # if self.start is not None:
            if self.start != None:
                self.start /= sampling_freq
            # if self.end is not None:
            if self.end != None:
                self.end /= sampling_freq
            if hasattr(self, 'duration') and self.duration is not None:

                self.duration /= sampling_freq

    @property
    def mean(self):
        """
        Calculate the mean of the current array.

        :return: Mean value of the current array.
        :rtype: float
        """
        return np.mean(self.current)

    @property
    def std(self):
        """
        Calculate the standard deviation of the current array.

        :return: Standard deviation of the current array.
        :rtype: float
        """
        return np.std(self.current)

    @property
    def min(self):
        """
        Calculate the minimum value of the current array.

        :return: Minimum value of the current array.
        :rtype: float
        """
        return np.min(self.current)

    @property
    def max(self):
        """
        Calculate the maximum value of the current array.

        :return: Maximum value of the current array.
        :rtype: float
        """
        return np.max(self.current)

    @property
    def n(self):
        """
        Get the number of elements in the current array.

        :return: Number of elements in the current array.
        :rtype: int
        """
        return len(self.current)

    @classmethod
    def from_json(self, filename=None, json=None):
        """
        Read in a segment from a JSON and return a metasegment object. Either
        pass in a file which has a segment stored, or an actual JSON object.
        """

        assert filename or json and not (filename and json)

        if filename:
            with open(filename, 'r') as infile:
                json = ''.join([line for line in infile])

        if 'current' not in json:
            return MetaSegment.from_json(json=json)

        words = re.findall(r"\[[\w\s'.-]+\]|[\w'.-]+", json)
        attrs = {words[i]: words[i+1] for i in range(0, len(words), 2)}

        current = np.array([float(x) for x in attrs['current'][1:-1].split()])
        del attrs['current']

        return Segment(current, **attrs)


@contextmanager
def ignored(*exceptions):
    """
    Replace the "try, except: pass" paradigm by replacing those three lines with a single line.
    Taken from the latest 3.4 python update push by Raymond Hettinger, see:
    http://hg.python.org/cpython/rev/406b47c64480
    """
    try:
        yield
    except exceptions:
        pass
