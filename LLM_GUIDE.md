# ionique — LLM Reference Guide

## Overview

ionique is a Python framework for nanopore ionic current signal analysis. It loads raw data files (`.edh`, `.opt`), organizes signals into a tree of hierarchical segments (voltage steps, events, sub-events), provides parsers for automated event detection, and exports features to DataFrames for statistical analysis. Python 3.10–3.13.

## Core Concepts

### Segment Tree

All data is organized in a tree. Each node is a segment with `start`/`end` indices into the root file's current array. Nodes have a `rank` string label and can contain `children`. Parsers create children at progressively deeper ranks.

### Rank Hierarchy (typical)

```
root (SessionFileManager)          — singleton session container
└── file (TraceFile)               — one loaded data file
    └── vstep                      — auto-created per voltage step
        └── vstepgap               — after Trimmer removes initial samples
            └── clean              — after ExclusionParser removes noisy regions
                └── event          — after AutoSquareParser detects blockades
                    └── subevent   — after SpeedyStatSplit segments within events
```

### Key Properties (MetaSegment / Segment)

All properties compute on-the-fly from the root file's current array:

| Property   | Type          | Description                              |
|------------|---------------|------------------------------------------|
| `current`  | `np.ndarray`  | Ionic current values for this segment    |
| `mean`     | `float`       | Mean of current                          |
| `std`      | `float`       | Standard deviation of current            |
| `min`      | `float`       | Minimum of current                       |
| `max`      | `float`       | Maximum of current                       |
| `time`     | `np.ndarray`  | Time array (seconds) for this segment    |
| `duration` | `float`       | `time[-1] - time[0]`                     |
| `n`        | `int`         | Number of samples (`end - start`)        |
| `start`    | `int`         | Start index (absolute, in root array)    |
| `end`      | `int`         | End index (absolute, in root array)      |

### Key Methods (AbstractSegmentTree)

| Method                                          | Description                                                    |
|-------------------------------------------------|----------------------------------------------------------------|
| `parse(parser, newrank, at_child_rank=None)`    | Run a parser; creates children with `newrank` at target rank   |
| `traverse_to_rank(rank) -> list`                | Collect all descendants at the given rank                      |
| `climb_to_rank(rank) -> segment or None`        | Walk up to the nearest ancestor with the given rank            |
| `get_feature(name)`                             | Get feature from self, `unique_features`, or climb ancestors   |
| `summary() -> dict`                             | `{rank: count}` for all ranks in the subtree                  |
| `add_child(child)` / `add_children(children)`   | Add child segment(s); validates bounds and no overlap          |

---

## Canonical Workflows

### 1. Load OPT files (programmatic)

```python
from ionique.io import OPTReader
from ionique.datatypes import SessionFileManager, TraceFile
from ionique.utils import Filter, Trimmer

sfm = SessionFileManager()

# Optional: pre-filter before loading
filt = Filter(cutoff_frequency=25000, filter_type="lowpass",
              filter_method="bessel", order=2, bidirectional=True,
              sampling_frequency=250000)

metadata, current, voltage = OPTReader(
    "path/to/file.opt",
    voltage_compress=True,   # splits by voltage steps
    downsample=5,
    prefilter=filt,
)

trace = TraceFile(
    current=current,
    voltage=voltage,
    parent=sfm,
    metadata=metadata,
    unique_features={
        "sampling_freq": metadata["eff_sampling_freq"],
        "eff_sampling_freq": metadata["eff_sampling_freq"],
    },
)
```

### 2. Load EDH files

```python
from ionique.io import EDHReader

metadata, current, voltage = EDHReader(
    "path/to/file.edh",
    voltage_compress=True,
    downsample=1,
    n_remove=0,
    prefilter=None,
)
# Then create TraceFile the same way as above.
```

### 3. Trim voltage steps

```python
from ionique.utils import Trimmer

trimmer = Trimmer(samples_to_remove=2000, rank="vstep", newrank="vstepgap")
trimmer(trace)
```

### 4. Exclude noisy regions

```python
from ionique.parsers import ExclusionParser

# Regions in global seconds to exclude
exclusion = ExclusionParser(regions=[(2.5, 4.0), (10.0, 11.5)])
trace.parse(exclusion, newrank="clean", at_child_rank="vstepgap")
```

### 5. Detect events with AutoSquareParser

```python
from ionique.parsers import AutoSquareParser

parser = AutoSquareParser(
    threshold_baseline=0.7,       # fraction of baseline for detection
    expected_conductance=2.0,     # nS
    conductance_tolerance=1.15,   # multiplicative tolerance
    wrap_padding=50,              # context samples around each event
    rules=[lambda event: event.duration > 4],
)
# Parse at the "clean" rank (or "vstepgap" if no exclusion step)
sfm.parse(parser, newrank="event", at_child_rank="clean")
```

### 6. Sub-event detection with SpeedyStatSplit

```python
from ionique.parsers import SpeedyStatSplit

sss = SpeedyStatSplit(
    sampling_freq=metadata["eff_sampling_freq"],
    min_width=5,
    window_width=500,
    false_positive_rate=5000,
    cutoff_freq=25000,
)
sfm.parse(parser=sss, newrank="subevent", at_child_rank="event")
```

### 7. Extract features into a DataFrame

```python
from ionique.utils import extract_features
import numpy as np

df = extract_features(
    sfm,
    bottom_rank="event",
    extractions=["mean", "std", "frac", "duration", "current", "wrap", "start"],
    lambdas={
        "Voltage": lambda seg: int(1000 * seg.get_feature("voltage")),
        "start_time": lambda seg: seg.time[0],
        "baseline": lambda seg: seg.unique_features["baseline"],
    },
    add_ons={"sample_type": "my_sample"},
)
```

### 8. Use `get_standard_features` (convenience)

```python
from ionique.simple import get_standard_features

df = get_standard_features()
# Returns DataFrame with: mean, std, frac, duration, current, wrap, start,
# filename, baseline, Voltage, baseline_conductance, start_time,
# parent_start_time, and subevent columns if subevents exist.
```

### 9. Plot with qp_trace

```python
from ionique.plotting import qp_trace

# Plot all files in the session
qp_trace()

# Plot a specific trace at custom ranks
qp_trace(trace, ranks=["vstepgap", "event"],
         downsamples={"vstepgap": 50, "event": 1},
         plot_voltage="split")
```

### 10. Filtering signals

```python
from ionique.utils import Filter, ClockFilter

# Low-pass filter (applied in-place)
lpf = Filter(cutoff_frequency=25000, filter_type="lowpass",
             filter_method="bessel", order=2, bidirectional=True,
             sampling_frequency=250000)
lpf(current_array)

# Remove clock interference (in-place)
clock = ClockFilter(clock_frequency=62500, section_length=0.5,
                    sampling_frequency=250000)
clock(current_array)
```

### 11. Saving results

```python
# Pickle (preserves array columns)
df.to_pickle("results.pkl")

# CSV (array columns must be dropped)
scalar_cols = [c for c in df.columns if not isinstance(df[c].iloc[0], np.ndarray)]
df[scalar_cols].to_csv("results.csv", index=False)
```

### 12. Interactive Panel/GUI workflow (Jupyter)

```python
from ionique.simple import (
    panel_load_opt_files,
    panel_parser_AutoSquare,
    panel_parser_SpeedyStatSplit,
    panel_parser_Exclusion,
    panel_save_dataframe,
    get_standard_features,
)
from ionique.plotting import dashboard_event_inspection

# Step 1: Load files
panel_load_opt_files(path="~/data", pattern="*[0-9].opt")

# Step 2: (Optional) Exclude noisy regions
panel_parser_Exclusion()

# Step 3: Detect events
panel_parser_AutoSquare()

# Step 4: Detect sub-events
panel_parser_SpeedyStatSplit()

# Step 5: Extract features
df = get_standard_features()

# Step 6: Interactive dashboard
dashboard_event_inspection(df)

# Step 7: Save
panel_save_dataframe(df)
```

---

## API Quick-Reference

### `ionique.io`

| Class | Constructor | Returns |
|-------|-------------|---------|
| `EDHReader(edh_filename, voltage_compress=False, n_remove=0, downsample=1, prefilter=None)` | Reads `.edh` + associated `.abf`/`.dat` files | Unpacks to `(metadata, current, voltage)` |
| `OPTReader(opt_filename, voltage_compress=False, n_remove=0, downsample=1, prefilter=None)` | Reads `.opt` + associated `.xml`/`_volt.opt` files | Unpacks to `(metadata, current, voltage)` |

When `voltage_compress=True`, voltage is `list[((start, end), voltage_value)]` instead of an array.

### `ionique.datatypes`

| Class | Constructor | Notes |
|-------|-------------|-------|
| `TraceFile(current, voltage=None, rank="file", parent=None, unique_features={}, metadata={})` | Creates a file-level Segment; auto-creates `vstep` children from voltage | Set `parent=sfm` to auto-add to session |
| `SessionFileManager()` | Singleton; call with no args to get the current session | Rank is always `"root"` |

### `ionique.core`

| Class | Constructor | Notes |
|-------|-------------|-------|
| `MetaSegment(start, end, parent=None, rank=None, unique_features={})` | Lightweight node; `current`/`mean`/`std` are computed on-the-fly from root file | Used by parsers to represent detected segments |
| `Segment(current, **kwargs)` | Data-containing node with a numpy array | `kwargs` can set `start`, `end`, `rank`, etc. |

### `ionique.parsers`

| Class | Constructor | Required Parent Attrs | Output Rank |
|-------|-------------|----------------------|-------------|
| `AutoSquareParser(threshold_baseline=0.7, expected_conductance=1.9, conductance_tolerance=1.2, wrap_padding=50, rules=[])` | `current`, `eff_sampling_freq`, `voltage` | `event` |
| `SpeedyStatSplit(sampling_freq, min_width=100, max_width=1000000, window_width=10000, min_gain_per_sample=None, false_positive_rate=None, prior_segments_per_second=None, cutoff_freq=None)` | `current` | `subevent` |
| `SpikeParser(height=None, threshold=None, distance=None, prominence=None, width=None, fractional=True, ...)` | `current`, `sampling_freq`, `mean`, `start`, `std` | varies |
| `ExclusionParser(regions=[(start_sec, end_sec), ...])` | `current`, `eff_sampling_freq`, `voltage`, `start` | `clean` |

### `ionique.utils`

| Name | Signature | Description |
|------|-----------|-------------|
| `Filter(cutoff_frequency, filter_type, filter_method="butter", order=2, bidirectional=True, sampling_frequency=None)` | Dataclass; callable on `(current, sampling_frequency=None)` | SOS low/high/band-pass filter, modifies array in-place |
| `ClockFilter(clock_frequency, section_length=0.5, sampling_frequency=None)` | Dataclass; callable on `(current, sampling_frequency=None)` | Removes single periodic frequency by sine subtraction, in-place |
| `Trimmer(samples_to_remove, rank="vstep", newrank="vstepgap")` | Callable on `(trace_file)` | Trims N samples from start of each segment at `rank` |
| `extract_features(seg, bottom_rank, extractions, add_ons={}, lambdas={})` | Returns `pd.DataFrame` | Extracts features from all segments at `bottom_rank` |
| `split_voltage_steps(voltage, n_remove=0, as_tuples=False)` | Returns indices or tuples | Splits voltage array at step changes |

### `ionique.plotting`

| Function | Signature | Description |
|----------|-----------|-------------|
| `qp_trace(seg=None, ranks=["vstepgap","event"], downsamples={"vstepgap":50,"event":1}, fig_size=(6,5), ranks_kwargs={}, fig_kwargs={}, plot_voltage=None)` | Matplotlib quick-plot | Plots trace at specified ranks; `plot_voltage`: `None`, `"same"`, or `"split"` |
| `dashboard_event_inspection(df)` | Panel+Bokeh interactive dashboard | Scatter plot + event viewer; expects DataFrame from `get_standard_features` |

### `ionique.simple`

| Function | Description |
|----------|-------------|
| `panel_load_opt_files(path="~", pattern="*[0-9].opt")` | Panel card for loading OPT files with filter/downsample controls |
| `panel_load_edh_files(path="~", pattern="*.edh")` | Panel card for EDH files (not yet implemented) |
| `panel_parser_AutoSquare()` | Panel card for configuring and running AutoSquareParser |
| `panel_parser_SpeedyStatSplit()` | Panel card for configuring and running SpeedyStatSplit |
| `panel_parser_Exclusion()` | Panel card for excluding noisy time regions |
| `panel_save_dataframe(df=None, start_dir=".")` | Panel card for saving DataFrame as `.pkl`, `.csv`, or `.xlsx` |
| `get_standard_features() -> pd.DataFrame` | Extracts standard event features from the current session |

---

## Feature Extraction Patterns

### `extract_features` (flexible)

```python
df = extract_features(
    seg,                          # any segment (usually sfm or trace)
    bottom_rank="event",          # rank to extract from
    extractions=["mean", "frac", "duration"],  # direct get_feature() calls
    add_ons={"label": "sample_A"},             # constant columns
    lambdas={                                   # computed columns
        "Voltage_mV": lambda s: int(1000 * s.get_feature("voltage")),
        "start_time": lambda s: s.time[0],
    },
)
```

- `extractions`: each name is resolved via `get_feature()` on the bottom-rank segment, which climbs the tree if the feature isn't local.
- `add_ons`: constant key-value pairs added to every row.
- `lambdas`: functions receiving each bottom-rank segment; can access any tree feature.

### `get_standard_features` (convenience)

Returns a DataFrame with these columns:

| Column | Source |
|--------|--------|
| `mean`, `std`, `frac`, `duration`, `current`, `wrap`, `start` | Direct segment properties |
| `filename` | `event.get_feature("metadata")["HeaderFile"]` |
| `baseline` | `event.unique_features["baseline"]` (sign-adjusted) |
| `Voltage` | Voltage in mV (integer) |
| `baseline_conductance` | `abs(baseline / voltage)` |
| `start_time` | `event.time[0]` |
| `parent_start_time` | `event.parent.time[0]` |
| `subevent_starts/ends/mean/std/duration/count` | Only if subevents exist |

---

## Common Pitfalls and Tips

1. **SessionFileManager is a singleton.** Call `SessionFileManager()` to get the existing session. Creating it again returns the same instance.

2. **`voltage_compress=True` is required** when loading files for step-wise analysis. Without it, voltage steps won't be detected and `vstep` children won't be created.

3. **MetaSegment properties are computed on-the-fly.** `mean`, `std`, `current`, `time` all climb to the `file` rank and slice the root array. This is efficient (no data duplication) but means the root `TraceFile` must stay in memory.

4. **`get_feature()` climbs the tree.** If a feature (e.g., `voltage`, `sampling_freq`) isn't on the current segment, it walks up through parents. This is how events access file-level metadata.

5. **Use `seg.summary()`** to inspect the current tree structure:
   ```python
   sfm.summary()
   # {'root': 1, 'file': 2, 'vstep': 10, 'vstepgap': 10, 'event': 47, 'subevent': 312}
   ```

6. **`unique_features` dict** is where parsers store per-segment metadata (e.g., `baseline`, `frac`, `wrap`, `voltage`). Access via `seg.unique_features["key"]` or `seg.get_feature("key")`.

7. **Filter and ClockFilter modify arrays in-place.** They don't return a new array. Pass them as `prefilter=` to readers, or call them directly on the current array before creating a TraceFile.

8. **`eff_sampling_freq`** is the effective sampling frequency after downsampling (`SR / downsample`). This is what parsers use, not the raw `Sampling frequency (SR)`.

9. **Parsing flow:** Always parse from outer to inner ranks: Trimmer -> ExclusionParser -> AutoSquareParser -> SpeedyStatSplit. Each parser creates children at the rank below.

10. **`at_child_rank` in `parse()`** tells the tree which rank to target. E.g., `sfm.parse(parser, newrank="event", at_child_rank="clean")` traverses down to all `clean` segments and parses each one independently.

---

## Writing Custom Modules

ionique is designed around abstract base classes that make it straightforward to add support for new file formats, detection algorithms, or processing steps.

### Custom File Reader

Subclass `AbstractFileReader` and override `_read()`. The base class handles filename validation, keyword checking, and session registration automatically.

```python
from ionique.io import AbstractFileReader
import numpy as np

class MyFormatReader(AbstractFileReader):
    ext = ".myf"                          # file extension to match
    accepted_keywords = ["voltage_compress", "downsample"]
    current_multiplier = 1e-9             # scale raw values to SI (Amps)
    voltage_multiplier = 1e-3             # scale raw values to SI (Volts)

    def __init__(self, filename, voltage_compress=False, downsample=1):
        super().__init__()                # registers with SessionFileManager
        self.filename = filename
        self.metadata, self.current, self.voltage = self._read()

    def __iter__(self):
        return iter((self.metadata, self.current, self.voltage))

    def _read(self):
        # Load your format here
        raw = np.fromfile(self.filename, dtype=np.float32)
        current = raw * self.current_multiplier
        voltage = np.zeros_like(current)  # or parse from header
        metadata = {
            "HeaderFile": self.filename,
            "Sampling frequency (SR)": 100000,
        }
        return metadata, current, voltage
```

**Key rules:** Set `ext` to your file extension (with dot). List `__init__` kwargs in `accepted_keywords`. Set multipliers to convert raw units to SI. `super().__init__()` auto-registers with the session. Override `_read()`, NOT `read()`. Return `(metadata_dict, current_array, voltage)`.

### Custom Parser

Subclass `Parser` (from `ionique.parsers`) and implement `__init__` and `parse()`. The `parse()` method receives parent-segment attributes and must return a list of `(start, end, unique_features_dict)` tuples.

```python
from ionique.parsers import Parser
import numpy as np

class ThresholdParser(Parser):
    # Attributes the parser needs from the parent segment.
    # The tree's parse() method calls get_feature() for each of these
    # and passes them as kwargs to your parse().
    required_parent_attributes = ["current", "eff_sampling_freq"]

    def __init__(self, threshold_fraction=0.5, min_samples=10):
        self.threshold_fraction = threshold_fraction
        self.min_samples = min_samples

    def parse(self, current, eff_sampling_freq):
        """Detect regions where current drops below a fraction of the median."""
        baseline = np.median(current)
        thresh = baseline * self.threshold_fraction
        below = current < thresh

        # Find contiguous regions
        edges = np.diff(below.astype(int))
        starts = np.where(edges == 1)[0] + 1
        ends = np.where(edges == -1)[0] + 1

        results = []
        for s, e in zip(starts, ends):
            if e - s >= self.min_samples:
                results.append((int(s), int(e), {
                    "mean": float(np.mean(current[s:e])),
                    "baseline": float(baseline),
                    "frac": 1 - np.mean(current[s:e]) / baseline,
                }))
        return results
```

**Key rules:** Set `required_parent_attributes` to feature names your `parse()` needs — the tree resolves each via `get_feature()` and passes them as kwargs. `parse()` must return `list[tuple[int, int, dict]]` — `(start, end, unique_features)` with indices relative to the `current` array passed in. The `unique_features` dict is stored on each resulting `MetaSegment`.

**Using your custom parser:**

```python
parser = ThresholdParser(threshold_fraction=0.6, min_samples=20)
sfm.parse(parser, newrank="my_event", at_child_rank="vstepgap")
```

### Custom Processing Step (callable pattern)

For non-parser transformations (like `Trimmer` or `Filter`), the convention is a dataclass with `__call__`:

```python
from dataclasses import dataclass
from ionique.core import MetaSegment

@dataclass
class MyProcessor:
    some_param: float
    rank: str = "event"
    newrank: str = "processed_event"

    def __call__(self, trace_file):
        for seg in trace_file.traverse_to_rank(self.rank):
            # Create modified children
            new_start = seg.start + 10  # example: skip first 10 samples
            if new_start < seg.end:
                seg.add_child(MetaSegment(
                    start=new_start, end=seg.end,
                    rank=self.newrank, parent=seg,
                ))
```

### Custom Rank Names

Rank names are arbitrary strings. You can introduce any rank name as long as you're consistent between parsing and extraction:

```python
# Parse with custom rank names
sfm.parse(my_parser, newrank="filtered_region", at_child_rank="vstepgap")
sfm.parse(event_parser, newrank="my_event", at_child_rank="filtered_region")

# Extract from your custom rank
df = extract_features(sfm, bottom_rank="my_event", extractions=["mean", "duration"])
```

---

## Additional Tips

11. **Inspect the tree interactively.** Use `traverse_to_rank` to get segments at any level and check their properties:
    ```python
    events = sfm.traverse_to_rank("event")
    print(len(events), events[0].mean, events[0].duration)
    ```

12. **Parsers are stateless between calls.** The same parser instance can be reused across multiple `parse()` calls or sessions. Configuration is set at construction time.

13. **`unique_features` propagates through `get_feature()`.** If you store `{"my_key": value}` on a `vstep` segment, any descendant (event, subevent) can retrieve it with `seg.get_feature("my_key")` without it being explicitly on the child.

14. **Custom lambdas in `extract_features` have full tree access.** The lambda receives the bottom-rank segment, from which you can navigate anywhere:
    ```python
    lambdas={
        "file_name": lambda s: s.climb_to_rank("file").metadata["HeaderFile"],
        "vstep_voltage": lambda s: s.climb_to_rank("vstep").unique_features["voltage"],
        "n_siblings": lambda s: len(s.parent.children),
    }
    ```

15. **Readers auto-register with SessionFileManager.** Every `AbstractFileReader` subclass calls `sfm.register_affector(self)` in `__init__`. This logs the reader in `sfm.affector_table` with a UUID and timestamp for provenance tracking.

16. **Segment validation is strict.** `add_children()` asserts that children are within parent bounds and don't overlap. If you get assertion errors, check that your parser returns non-overlapping `(start, end)` tuples within the parent segment's range.

17. **`MetaSegment` vs `Segment`.** Parsers create `MetaSegment` children (lightweight, no data copy). `Segment` holds its own `current` array and is used only for `TraceFile` and legacy parsers. Prefer `MetaSegment` in custom parsers — it slices the root array on demand.

18. **Multiple files in one session.** Load multiple files into the same session by setting `parent=sfm` on each `TraceFile`. All tree operations (`parse`, `traverse_to_rank`, `extract_features`) then operate across all files at once.

19. **Resetting the session.** `SessionFileManager` is a singleton that persists for the Python process. To start fresh in a notebook, restart the kernel. There is no public `reset()` method.

20. **DataFrame array columns.** Columns like `current`, `wrap`, `subevent_starts` contain numpy arrays. These survive `.to_pickle()` but are dropped or cause errors with `.to_csv()`. Use `panel_save_dataframe()` or manually drop array columns before CSV export.
