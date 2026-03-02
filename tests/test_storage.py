"""
Tests for ionique.storage — HDF5 save/load roundtrip, LazyArray, source switching.
"""

import numpy as np
import pytest
import h5py

from ionique.core import MetaSegment, Segment
from ionique.datatypes import TraceFile, SessionFileManager
from ionique.storage import LazyArray, save, load, IQ5_EXTENSION, _walk_node_paths


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_current():
    np.random.seed(42)
    return np.random.randn(5000).astype(np.float32)


@pytest.fixture
def trace_with_vsteps(sample_current):
    """A TraceFile with two voltage steps and known current."""
    voltage = [((0, 2500), 0.1), ((2500, 5000), 0.2)]
    return TraceFile(
        current=sample_current,
        voltage=voltage,
        unique_features={"sampling_freq": 250000},
        metadata={"experiment": "test", "operator": "ci"},
    )


@pytest.fixture
def h5_path(tmp_path):
    return str(tmp_path / "test_output.iq5")


# ---------------------------------------------------------------------------
# LazyArray basic behaviour
# ---------------------------------------------------------------------------

class TestLazyArray:
    def test_getitem_returns_numpy(self, trace_with_vsteps, h5_path, sample_current):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        sliced = loaded.current[100:200]
        assert isinstance(sliced, np.ndarray)
        np.testing.assert_array_almost_equal(sliced, sample_current[100:200])

    def test_len(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        assert len(loaded.current) == 5000

    def test_shape_dtype_ndim_size(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        assert loaded.current.shape == (5000,)
        assert loaded.current.dtype == np.float32
        assert loaded.current.ndim == 1
        assert loaded.current.size == 5000

    def test_np_asarray(self, trace_with_vsteps, h5_path, sample_current):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        arr = np.asarray(loaded.current)
        assert isinstance(arr, np.ndarray)
        np.testing.assert_array_almost_equal(arr, sample_current)

    def test_np_mean(self, trace_with_vsteps, h5_path, sample_current):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        np.testing.assert_almost_equal(
            np.mean(loaded.current), np.mean(sample_current), decimal=5
        )

    def test_setitem(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        loaded.current[0:3] = np.array([9.0, 8.0, 7.0], dtype=np.float32)
        np.testing.assert_array_almost_equal(
            loaded.current[0:3], [9.0, 8.0, 7.0]
        )

    def test_repr(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        r = repr(loaded.current)
        assert "LazyArray" in r
        assert "raw" in r


# ---------------------------------------------------------------------------
# Save / Load roundtrip — TraceFile
# ---------------------------------------------------------------------------

class TestTraceFileRoundtrip:
    def test_current_roundtrip(self, trace_with_vsteps, h5_path, sample_current):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        np.testing.assert_array_almost_equal(loaded.current[:], sample_current)

    def test_time_roundtrip(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        expected_time = np.arange(0, 5000) / 250000
        np.testing.assert_array_almost_equal(loaded.time[:], expected_time)

    def test_metadata_preserved(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        assert loaded.metadata["experiment"] == "test"
        assert loaded.metadata["operator"] == "ci"

    def test_rank_and_position(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        assert loaded.rank == "file"
        assert loaded.start == 0
        assert loaded.end == 5000

    def test_sampling_freq(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        assert loaded.sampling_freq == 250000

    def test_voltage_steps_restored(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        assert loaded.voltage is not None
        assert len(loaded.voltage) == 2
        assert loaded.voltage[0] == ((0, 2500), 0.1)

    def test_children_preserved(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        assert len(loaded.children) == 2
        assert loaded.children[0].rank == "vstep"
        assert loaded.children[0].start == 0
        assert loaded.children[0].end == 2500
        assert loaded.children[0].unique_features["voltage"] == 0.1

    def test_metasegment_current_via_climb(self, trace_with_vsteps, h5_path, sample_current):
        """MetaSegment.current climbs to file and slices — must work with LazyArray."""
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        vstep = loaded.children[0]
        cur = vstep.current
        assert cur is not None
        np.testing.assert_array_almost_equal(cur, sample_current[0:2500])

    def test_metasegment_stats(self, trace_with_vsteps, h5_path, sample_current):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        vstep = loaded.children[0]
        expected_mean = np.mean(sample_current[0:2500])
        np.testing.assert_almost_equal(vstep.mean, expected_mean, decimal=5)

    def test_summary_matches(self, trace_with_vsteps, h5_path):
        original_summary = trace_with_vsteps.summary()
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        assert loaded.summary() == original_summary


# ---------------------------------------------------------------------------
# Save / Load roundtrip — Segment
# ---------------------------------------------------------------------------

class TestSegmentRoundtrip:
    def test_segment_roundtrip(self, h5_path):
        current = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        seg = Segment(current=current, start=0, end=5, rank="event")
        save(seg, h5_path)
        loaded = load(h5_path)
        np.testing.assert_array_equal(loaded.current[:], current)
        assert loaded.rank == "event"
        assert loaded.start == 0
        assert loaded.end == 5


# ---------------------------------------------------------------------------
# Save / Load roundtrip — MetaSegment
# ---------------------------------------------------------------------------

class TestMetaSegmentRoundtrip:
    def test_metasegment_roundtrip(self, h5_path):
        ms = MetaSegment(start=10, end=20, rank="subevent",
                         unique_features={"baseline": 1.8e-9, "frac": 0.27})
        save(ms, h5_path)
        loaded = load(h5_path)
        assert loaded.start == 10
        assert loaded.end == 20
        assert loaded.rank == "subevent"
        assert loaded.unique_features["baseline"] == pytest.approx(1.8e-9)
        assert loaded.unique_features["frac"] == pytest.approx(0.27)


# ---------------------------------------------------------------------------
# Array-valued unique_features
# ---------------------------------------------------------------------------

class TestArrayFeatures:
    def test_array_feature_roundtrip(self, h5_path):
        wrap = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
        ms = MetaSegment(start=0, end=100, rank="event",
                         unique_features={"wrap": wrap, "scalar_feat": 42.0})
        save(ms, h5_path)
        loaded = load(h5_path)
        np.testing.assert_array_almost_equal(
            loaded.unique_features["wrap"], wrap
        )
        assert loaded.unique_features["scalar_feat"] == 42.0


# ---------------------------------------------------------------------------
# Source switching
# ---------------------------------------------------------------------------

class TestSourceSwitching:
    def test_add_and_switch_source(self, trace_with_vsteps, h5_path, sample_current):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)

        # Add a filtered version (just multiply by 2 for testing)
        filtered = sample_current * 2.0
        loaded.add_source("filtered_test", filtered)

        # Switch to filtered source
        loaded.switch_source("filtered_test")
        assert loaded.current.active_source == "filtered_test"
        np.testing.assert_array_almost_equal(
            loaded.current[:], filtered
        )

        # Switch back to raw
        loaded.switch_source("raw")
        np.testing.assert_array_almost_equal(
            loaded.current[:], sample_current
        )

    def test_switch_source_invalid(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        with pytest.raises(KeyError):
            loaded.switch_source("nonexistent")

    def test_add_source_on_numpy_raises(self, trace_with_vsteps):
        with pytest.raises(TypeError, match="HDF5-backed"):
            trace_with_vsteps.add_source("x", np.zeros(10))

    def test_metasegment_reads_switched_source(self, trace_with_vsteps, h5_path, sample_current):
        """After switch_source, MetaSegment.current should return filtered data."""
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        filtered = sample_current * 3.0
        loaded.add_source("filtered_3x", filtered)
        loaded.switch_source("filtered_3x")

        vstep = loaded.children[0]
        expected = filtered[0:2500]
        np.testing.assert_array_almost_equal(vstep.current, expected)

    def test_available_sources(self, trace_with_vsteps, h5_path, sample_current):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)
        assert loaded.current.available_sources == ["raw"]
        loaded.add_source("alt", sample_current * 0.5)
        sources = sorted(loaded.current.available_sources)
        assert sources == ["alt", "raw"]


# ---------------------------------------------------------------------------
# Nested tree roundtrip
# ---------------------------------------------------------------------------

class TestNestedTreeRoundtrip:
    def test_deep_tree(self, trace_with_vsteps, h5_path):
        """Add events under vsteps and verify the full tree survives roundtrip."""
        vstep = trace_with_vsteps.children[0]
        event1 = MetaSegment(start=100, end=200, parent=vstep, rank="event",
                             unique_features={"baseline": 1.5e-9})
        event2 = MetaSegment(start=300, end=400, parent=vstep, rank="event",
                             unique_features={"baseline": 1.6e-9})
        vstep.add_children([event1, event2])

        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)

        loaded_vstep = loaded.children[0]
        assert len(loaded_vstep.children) == 2
        assert loaded_vstep.children[0].rank == "event"
        assert loaded_vstep.children[0].start == 100
        assert loaded_vstep.children[0].end == 200
        assert loaded_vstep.children[0].unique_features["baseline"] == pytest.approx(1.5e-9)


# ---------------------------------------------------------------------------
# HDF5 file format
# ---------------------------------------------------------------------------

class TestFileFormat:
    def test_format_version(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        with h5py.File(h5_path, "r") as f:
            assert f.attrs["format_version"] == "1.0"

    def test_compression(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        with h5py.File(h5_path, "r") as f:
            ds = f["root/sources/raw/current"]
            assert ds.compression == "gzip"
            assert ds.compression_opts == 4


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_save_load_resave(self, trace_with_vsteps, h5_path, tmp_path, sample_current):
        """Save, load (lazy), then save again to a new file."""
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)

        h5_path2 = str(tmp_path / "resaved.iq5")
        save(loaded, h5_path2)

        reloaded = load(h5_path2)
        np.testing.assert_array_almost_equal(reloaded.current[:], sample_current)
        assert len(reloaded.children) == 2

    def test_empty_unique_features(self, h5_path):
        ms = MetaSegment(start=0, end=10, rank="x", unique_features={})
        save(ms, h5_path)
        loaded = load(h5_path)
        assert loaded.unique_features == {}


# ---------------------------------------------------------------------------
# IQ5 extension constant
# ---------------------------------------------------------------------------

class TestIQ5Extension:
    def test_iq5_extension_value(self):
        assert IQ5_EXTENSION == ".iq5"


# ---------------------------------------------------------------------------
# to_iq5() — purge to disk
# ---------------------------------------------------------------------------

class TestToIQ5:
    def test_to_iq5_returns_self(self, trace_with_vsteps, tmp_path):
        path = str(tmp_path / "purge.iq5")
        result = trace_with_vsteps.to_iq5(path)
        assert result is trace_with_vsteps

    def test_current_becomes_lazy(self, trace_with_vsteps, tmp_path):
        path = str(tmp_path / "purge.iq5")
        trace_with_vsteps.to_iq5(path)
        assert isinstance(trace_with_vsteps.current, LazyArray)

    def test_lazy_slicing_correct(self, trace_with_vsteps, tmp_path, sample_current):
        path = str(tmp_path / "purge.iq5")
        trace_with_vsteps.to_iq5(path)
        np.testing.assert_array_almost_equal(
            trace_with_vsteps.current[100:200], sample_current[100:200]
        )

    def test_iq5_path_set(self, trace_with_vsteps, tmp_path):
        path = str(tmp_path / "purge.iq5")
        trace_with_vsteps.to_iq5(path)
        assert trace_with_vsteps.iq5_path == path

    def test_grp_paths_set(self, trace_with_vsteps, tmp_path):
        path = str(tmp_path / "purge.iq5")
        trace_with_vsteps.to_iq5(path)
        assert trace_with_vsteps._iq5_grp_path == "root"
        for child in trace_with_vsteps.children:
            assert child._iq5_grp_path is not None

    def test_metasegment_current_after_purge(self, trace_with_vsteps, tmp_path,
                                              sample_current):
        path = str(tmp_path / "purge.iq5")
        trace_with_vsteps.to_iq5(path)
        vstep = trace_with_vsteps.children[0]
        cur = vstep.current
        assert cur is not None
        np.testing.assert_array_almost_equal(cur, sample_current[0:2500])


# ---------------------------------------------------------------------------
# sync_iq5() — incremental sync
# ---------------------------------------------------------------------------

class TestSyncIQ5:
    def test_sync_without_iq5_raises(self, trace_with_vsteps):
        with pytest.raises(RuntimeError, match="Not connected"):
            trace_with_vsteps.sync_iq5()

    def test_sync_after_adding_children(self, trace_with_vsteps, tmp_path,
                                         sample_current):
        path = str(tmp_path / "sync.iq5")
        trace_with_vsteps.to_iq5(path)

        # Add new children to the first vstep
        vstep = trace_with_vsteps.children[0]
        ev1 = MetaSegment(start=100, end=200, parent=vstep, rank="event",
                          unique_features={"baseline": 1.5e-9})
        ev2 = MetaSegment(start=300, end=400, parent=vstep, rank="event",
                          unique_features={"baseline": 1.6e-9})
        vstep.add_children([ev1, ev2])

        trace_with_vsteps.sync_iq5()

        # Reload and verify
        reloaded = load(path)
        assert len(reloaded.children[0].children) == 2
        assert reloaded.children[0].children[0].rank == "event"
        assert reloaded.children[0].children[0].start == 100

    def test_sync_after_clear_and_add(self, trace_with_vsteps, tmp_path):
        path = str(tmp_path / "sync_clear.iq5")

        # Add initial events
        vstep = trace_with_vsteps.children[0]
        ev1 = MetaSegment(start=100, end=200, parent=vstep, rank="event")
        vstep.add_children([ev1])
        trace_with_vsteps.to_iq5(path)

        # Clear old children and add new
        vstep.clear_children()
        ev2 = MetaSegment(start=500, end=600, parent=vstep, rank="newevent")
        vstep.add_children([ev2])

        trace_with_vsteps.sync_iq5()

        # Reload and verify old children gone, new present
        reloaded = load(path)
        loaded_vstep = reloaded.children[0]
        assert len(loaded_vstep.children) == 1
        assert loaded_vstep.children[0].rank == "newevent"
        assert loaded_vstep.children[0].start == 500

    def test_sync_updates_features(self, trace_with_vsteps, tmp_path):
        path = str(tmp_path / "sync_feat.iq5")
        trace_with_vsteps.to_iq5(path)

        # Modify a unique_feature
        trace_with_vsteps.unique_features["new_key"] = 42.0
        trace_with_vsteps.sync_iq5()

        reloaded = load(path)
        assert reloaded.unique_features["new_key"] == 42.0

    def test_sync_assigns_paths_to_new_children(self, trace_with_vsteps,
                                                  tmp_path):
        path = str(tmp_path / "sync_paths.iq5")
        trace_with_vsteps.to_iq5(path)

        vstep = trace_with_vsteps.children[0]
        ev = MetaSegment(start=100, end=200, parent=vstep, rank="event")
        vstep.add_children([ev])

        trace_with_vsteps.sync_iq5()

        # After sync, the new child should have a grp_path
        assert ev._iq5_grp_path is not None
        assert ev._iq5_path == path


# ---------------------------------------------------------------------------
# load() sets _iq5_grp_path
# ---------------------------------------------------------------------------

class TestLoadSetsGrpPaths:
    def test_load_sets_grp_paths(self, trace_with_vsteps, h5_path):
        save(trace_with_vsteps, h5_path)
        loaded = load(h5_path)

        assert loaded._iq5_grp_path == "root"
        assert loaded._iq5_path == h5_path
        for node, grp_path in _walk_node_paths(loaded):
            assert node._iq5_grp_path == grp_path
            assert node._iq5_path == h5_path


# ---------------------------------------------------------------------------
# detach_iq5()
# ---------------------------------------------------------------------------

class TestDetachIQ5:
    def test_detach_returns_self(self, trace_with_vsteps, tmp_path):
        path = str(tmp_path / "detach.iq5")
        trace_with_vsteps.to_iq5(path)
        result = trace_with_vsteps.detach_iq5()
        assert result is trace_with_vsteps

    def test_detach_converts_to_numpy(self, trace_with_vsteps, tmp_path,
                                       sample_current):
        path = str(tmp_path / "detach.iq5")
        trace_with_vsteps.to_iq5(path)
        trace_with_vsteps.detach_iq5()

        assert isinstance(trace_with_vsteps.current, np.ndarray)
        np.testing.assert_array_almost_equal(
            trace_with_vsteps.current, sample_current
        )

    def test_detach_clears_iq5_path(self, trace_with_vsteps, tmp_path):
        path = str(tmp_path / "detach.iq5")
        trace_with_vsteps.to_iq5(path)
        trace_with_vsteps.detach_iq5()

        assert trace_with_vsteps.iq5_path is None
        for node, _ in _walk_node_paths(trace_with_vsteps):
            assert node._iq5_grp_path is None
