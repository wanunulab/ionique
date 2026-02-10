"""
Unit test for core.py
"""


import pytest
import numpy as np
from ionique.core import AbstractSegmentTree, MetaSegment, Segment


@pytest.fixture
def current_data():
    """Fixture to generate ionic current data"""
    return np.array([1.0, 2.0, 3.0, 4.0, 5.0])


@pytest.fixture
def segment_tree():
    """Fixture to generate AbstractSegmentTree instace"""
    return AbstractSegmentTree()


@pytest.fixture
def meta_segment():
    """Fixture to generate MetaSegment instance"""
    return MetaSegment(start=0, end=5, unique_features={"test_feature": "test_value"})


@pytest.fixture
def segment(current_data):
    """Fixture to generate Segment instance"""
    return Segment(current=current_data)


#############################################
#        AbstractSegmentTree
#############################################


# Test cass for AbstractSegmentTree Initialization
def test_abstract_segment_tree_init(segment_tree):
    """Test correct AbstractSegmentTree class initialization"""
    assert segment_tree.parent is None
    assert segment_tree.children == []
    assert segment_tree.end is None
    assert segment_tree.rank is None


# Test AbstractSegmentTree method get_feature
def test_abstract_tree_get_feature(meta_segment):
    """Test the get_feature method of AbstractSegmentTree"""
    assert meta_segment.get_feature("test_feature") == "test_value"
    assert meta_segment.get_feature("not_feature") is None


# Test AbstractSegmentTree methods add_child, add_children
def test_abstract_tree_add_child(segment_tree, meta_segment):
    """Test add_child method"""
    segment_tree.add_child(meta_segment)
    assert len(segment_tree.children) == 1
    assert segment_tree.children[0] == meta_segment


def test_abstract_tree_add_children(segment_tree):
    """Test add_children method"""
    # Add two segments to avoid overlapping
    meta1 = MetaSegment(start=0, end=5, unique_features={"feat1": "value1"})
    meta2 = MetaSegment(start=6, end=10, unique_features={"feat2": "value2"})
    segment_tree.add_children([meta1, meta2])
    assert len(segment_tree.children) == 2


# Test AbstractSegmentTree relative_start, relative_end
def test_abstract_tree_relative_start(meta_segment):
    """Test relative start and end
    relative_start = start - parent_start
    relative_end = end - parent_start
    """
    parent_seg = MetaSegment(start=0, end=10)  # set parent segment
    meta_segment.parent = parent_seg
    assert meta_segment.relative_start == 0
    assert meta_segment.relative_end == 5


# Test AbstractSegmentTree slice
def test_abstract_tree_slice(meta_segment):
    """Test relative slice
    slice = numpy_array(start:end)"""
    assert np.array_equal(meta_segment.slice, np.s_[0:5])


# Test AbstractSegmentTree relative slice
def test_abstract_tree_relative_slice(meta_segment):
    """Test relative slice
    relative_slice = numpy_array(relative_start:relative_end)"""
    assert np.array_equal(meta_segment.relative_slice, np.s_[0:5])


# Test AbstractSegmentTree length of segment
def test_abstract_tree_n(meta_segment):
    """Test length (n method)"""
    assert meta_segment.n == 5


# Test MetaSegment initialization
def test_meta_segment_init(meta_segment):
    """Test initialization of MetaSegment"""
    assert meta_segment.start == 0
    assert meta_segment.end == 5
    assert meta_segment.unique_features == {"test_feature": "test_value"}


###################################
#        Segment
###################################


# Test Segment initialization
def test_segment_init(segment):
    """Test segment initialization"""
    assert segment.n == 5
    assert np.array_equal(segment.current, np.array([1.0, 2.0, 3.0, 4.0, 5.0]))


# Test Segment  basic stats
def test_segment_stats(segment):
    """Test basic statistics in segment"""
    assert segment.mean == np.mean(segment.current)
    assert segment.std == np.std(segment.current)
    assert segment.min == np.min(segment.current)
    assert segment.max == np.max(segment.current)


# Test to_json, from_json
def test_to_json(segment):
    """Test to json method"""
    json_str = segment.to_json()
    assert '"mean"' in json_str
    assert '"std"' in json_str
    assert '"min"' in json_str
    assert '"max"' in json_str


## TODO: Might need to change core.py. Parsing json using loads
# def test_from_json(segment):
#     """Test from json methos to get Segment from JSON string"""
#     json_data = '{"current": "[1.0, 2.0, 3.0, 4.0, 5.0]"}'
#     segment = Segment.from_json(json=json_data)
#     assert np.array_equal(segment.current, current_data)
#








