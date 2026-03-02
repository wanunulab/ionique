#!/usr/bin/env python
"""
ionique: modular nanopore signal analysis framework for ionic current data.

Submodules
----------
core
    Segment tree hierarchy (AbstractSegmentTree, MetaSegment, Segment) for
    organizing and recursively parsing ionic current signal data. core is rarely imported by the user. 
datatypes
    Data containers including TraceFile for wrapping loaded traces and
    SessionFileManager (singleton) for managing a session's loaded files.
io
    File readers for nanopore data formats: EDH, OPT, and ABF. Handles
    loading, metadata extraction, and unit scaling.
utils
    Signal processing utilities such as filters and feature extraction helpers.
    
parsers
    Event detection parsers (SpikeParser, AutoSquareParser) that operate on
    Segment trees and produce child segments for detected events.
plotting
    Bokeh-based visualization functions and Panel-based interactive
    dashboards for exploring nanopore traces.
simple
    GUI/Jupyter convenience functions and Panel widgets for file loading and
    parser configuration, intended for non-programmatic use.

Notes
-----
``__version__`` is auto-generated from the package metadata by
setuptools-scm and exposed here so callers can inspect it via
``ionique.__version__``.  Falls back to ``"0.0.0"`` when the generated
``_version.py`` file is absent (e.g. in an uninstalled source tree).
"""
import ionique.core as core
import ionique.datatypes as datatypes
import ionique.io as io
import ionique.utils as utils
import ionique.parsers as parsers
import ionique.plotting as plotting
import ionique.simple as simple
import ionique.storage as storage

# show package version, this enables -> print(ionique.__version__)
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0"  # if _version.py is missing use this


__all__=["core","datatypes","io","utils","parsers","plotting","simple","storage"]
def __dir__():
    return sorted(list(set(list(globals().keys())+__all__)))
