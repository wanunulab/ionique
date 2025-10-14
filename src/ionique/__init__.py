#!/usr/bin/env python
import ionique.core as core
import ionique.datatypes as datatypes
import ionique.io as io
import ionique.utils as utils
import ionique.parsers as parsers
import ionique.plotting as plotting
import ionique.simple as simple

# show package version, this enables -> print(ionique.__version__)
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0"  # if _version.py is missing use this


__all__=["core","datatypes","io","utils","parsers","plotting","simple"]
def __dir__():
    return sorted(list(set(list(globals().keys())+__all__)))
