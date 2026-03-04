# Documentation Code Example Fixes

Fixes for incorrect API usages found in documentation code examples.

| File | Line | Before | After | Reason |
|------|------|--------|-------|--------|
| `docs/api/core.rst` | 199 | `SpikeParser(threshold_start=0.15, threshold_end=0.15, min_width=10, max_width=10000)` | `SpikeParser(prominence=0.15, distance=100, width=(10, 10000))` | Parameters `threshold_start`, `threshold_end`, `min_width`, `max_width` don't exist in SpikeParser. Actual params: `height`, `threshold`, `distance`, `prominence`, `width`, etc. |
| `docs/api/core.rst` | 227 | `from ionique.core import ignored` | Replaced section: notes `_ignored` is internal, recommends `contextlib.suppress` | Function is `_ignored` (private). Not importable as `ignored`. Replaced with standard library equivalent. |
| `docs/parsers_guide.rst` | 128 | `parser.to_json("my_parser.json")` | `parser.to_json(filename="my_parser.json")` | `to_json()` takes `filename` as keyword arg, not positional. |
| `docs/parsers_guide.rst` | 132 | `restored = Parser.from_json(json_str)` | Removed; added note that `from_json` is not yet implemented | `from_json` returns `None` (stub). Showing it as working is misleading. |
| `docs/parsers/other_parsers.rst` | 202 | `IVCurveParser(voltage=voltage_array)` | `IVCurveParser(voltage_array)` | `voltage` is a positional argument in the constructor. |
| `src/ionique/datatypes.py` | 183 | `getattr(self.unique_features,"sampling_freq",...)` | `self.unique_features.get("sampling_freq", self.metadata.get(...))` | `getattr` doesn't find dict keys; use `.get()` for dict fallback chain. |
| `README.md` | 21 | `TraceFile(*EDHReader(...))` | Unpack reader, pass named params | `*reader` unpacks `(metadata, current, voltage)` into wrong positional args. |
| `docs/index.rst` | 19–20 | `reader = ...; trace = TraceFile(*reader)` | Unpack reader, pass named params | Same `*reader` unpacking bug. |
| `docs/getting_started.rst` | 24–25 | `reader = ...; trace = TraceFile(*reader)` | Unpack reader, pass named params | Same `*reader` unpacking bug. |
| `docs/data_input.rst` | 117–120 | `TraceFile(*reader)` + misleading shorthand | Single correct `TraceFile(current, voltage=voltage, ...)` call | Removed broken pattern and misleading "shorthand" comment. |
| `docs/tutorial.rst` | 27 | `trace = TraceFile(*reader)` | Unpack reader, pass named params | Same `*reader` unpacking bug. |
| `docs/tutorial.rst` | 222 | `TraceFile(*EDHReader(...))` | Unpack reader, pass named params | Same `*reader` unpacking bug. |
| `docs/signal_analysis.rst` | 131 | `trace = TraceFile(*reader)` | Unpack reader, pass named params | Same `*reader` unpacking bug. |
