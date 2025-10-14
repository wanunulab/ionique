#!/usr/bin/env python
"""
Signal Processing and Data Extraction Utilities

This module provides a set of utility functions and classes designed for use in signal
processing workflows.

These tools are intended for both internal processing and external use cases such as analysis
pipelines and API integrations.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
import scipy.signal as signal
from typing import Literal
from ionique.core import MetaSegment

# try:
#     import cupy
#     import cupyx.scipy.signal as signal
#     if not cupy.cuda.is_available():
#         raise ImportError

#     np = cupy
# except ImportError:

#     import numpy as np
#     from scipy import signal


class Singleton(type):
    """
    Generic singleton metaclass.

    This metaclass ensures the same return every time the class is instanced.
    """

    def __init__(self, *args, **kwargs):
        """
        Class initialization

        :param args: Arguments for the class
        :param kwargs: Keyword arguments for the class
        """
        self.__instance = None
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        """
        Returns the Singleton instance.

        It creates the instance if it doesn't exist the instance does not exist.
        If the instance exists, it is returned as-is.

        :param args: Arguments for the class constructor.
        :param kwargs: Keyword arguments for the class constructor.
        :return: The Singleton instance.
        :rtype: object
        """
        if self.__instance is None:
            self.__instance = super().__call__(*args, **kwargs)
        return self.__instance


def split_voltage_steps(voltage: np.ndarray, n_remove=0, as_tuples=False):
    """
    Split a voltage signal into segments based on step changes.

    This function detects changes in the voltage signal and splits it into individual
    segments (or steps) wherever a change in value occurs. It is useful in analyzing
    stepwise voltage protocols.

    Optionally, a number of initial samples can be removed from each segment using the
    `n_remove` parameter. The output can either be two separate arrays of start and end
    indices, or a list of tuples representing each segment.

    :param voltage: 1D voltage signal array to be segmented.
    :type voltage: numpy.ndarray
    :param n_remove: Number of samples to remove from the start of each split. Defaults to 0.
    :type n_remove: int
    :param as_tuples: If True, returns a list of (start, end) index tuples. If False, returns two arrays: start_indices and end_indices. Defaults to False.
    :type as_tuples: bool
    :raises ValueError:  If `n_remove` is negative or larger than the start of the voltage changes.
    :return: Either:
              - A tuple of (start_indices, end_indices), where each is a numpy array of indices.
              - A list of (start, end) tuples if `as_tuples=True`.
    :rtype: tuple[numpy.ndarray, numpy.ndarray] or list[tuple[int, int]]
    """

    # Check if the current or voltage arrays are empty
    if not voltage.size:
        return []
    # Check if the n_remove argument is negative
    if n_remove < 0:
        raise ValueError("n_remove must be non-negative")
    # Find the indices at which the voltage level changes
    split_indices = np.where(voltage[:-1] != voltage[1:])[0] + 1
    # Add the start and end indices of the current array to the split indices
    split_indices = np.concatenate([[0], split_indices, [len(voltage)]])
    # Calculate the start and end indices of the splits
    start_indices = split_indices[:-1] + n_remove
    end_indices = split_indices[1:]
    # Check if n_remove is not too large
    if np.any(end_indices <= start_indices):
        raise ValueError("n_remove is too large")
    if not as_tuples:
        return start_indices, end_indices
    # Optional: return list of tuples of start and end
    return [(start_ind, end_ind) for start_ind, end_ind in zip(start_indices, end_indices)]


def si_eval(value, unit=None, return_unit=False):
    """
    Evaluate and convert a value with an SI unit prefix to its numeric base value.

    This function handles both string-based and numeric values with
    SI (International System of Units) prefixes such as "k" (kilo), "M" (mega), "μ" (micro), etc.
    It multiplies the input value by the appropriate factor based on the SI prefix.

    This utility is useful when parsing human-readable measurement strings or standardizing
    units across data pipelines that mix strings and numeric formats.

    :param value: The value to be converted. Can be a string like "1.2 kHz" or a numeric value (int or float).
    :type value: str or float
    :param unit: The unit string (e.g., "kHz", "mV"). Required only if `value` is a numeric type.
    :type unit: str, optional
    :param return_unit: If True, returns a tuple containing the converted numeric value and the base unit (e.g., 'Hz').
                        If False, only the numeric value is returned.
    :type return_unit: bool, optional
    :raises ValueError: If the input format is invalid or the unit is missing for numeric input.
    :raises TypeError: If the value is neither a string nor a numeric type.
    :return: The converted value, optionally paired with the base unit.
    :rtype: float or tuple[float, str]
    """
    # If value is a string, split it to separate the value from unit
    if isinstance(value, str):
        try:
            numeric_val, unit_full = value.strip().split()
            numeric_val = float(numeric_val)
            final_value = numeric_val * _si_multiplier_unit(unit_full[0])
        except ValueError:
            print(f"Invalid value format: {value}. Should be '"
                             f"number unit'(Ex:'1.2 kHz')")

    # If value is a numer:
    elif isinstance(value, (int, float)):
        if unit is None:
            raise ValueError("Unit is not provided. Ex: 1.2, 'kHz'")
        final_value = value * _si_multiplier_unit(unit[0])
    else:
        raise TypeError("Provide the parameters!")
    if return_unit:
        return final_value, unit[1:]
    return final_value


def _get_prefix_val() -> dict:
    """
    Return a dictionary of SI prefixes and the corresponding multiplier values.

    This function is used internally to provide the SI prefix values.

    :return: A dictionary mapping SI prefixes to their values.
    :rtype: dict
    """

    prefix = {
        "f": 1e-15,
        "p": 1e-12,
        "n": 1e-9,
        "u": 1e-6,
        "μ": 1e-6,
        "m": 1e-3,
        "c": 1e-2,
        "k": 1e3,
        "M": 1e6,
        "G": 1e9,
        "T": 1e12,
    }
    return prefix


def _si_multiplier_unit(unitstr: str) -> float:
    """
    Return a multiplier for a given unit prefix.

    Given a single character string (SI prefix) it
    returns the corresponding multiplier value.

    :param unitstr: A single character string = SI prefix.
    :type unitstr: str
    :return: The multiplier corresponding to the given SI prefix.
    :rtype: float
    """

    if unitstr in _get_prefix_val():
        return _get_prefix_val()[unitstr]

    raise ValueError(f"Unit prefix is not known: {unitstr}, see available:\n{_get_prefix_val()}")

@dataclass
class Filter:
    """
    This class allows a user to apply low-pass, high-pass,
    band-pass, or band-stop filters using standard filter types (Butterworth or Bessel).
    Filters are implemented using second-order sections (SOS) for numerical stability and
    can be applied in either forward-only or bidirectional mode.

    :param cutoff_frequency: The cutoff frequency or frequency band for the filter in Hz.
                            For band filters, provide the band center or list of [low, high] values.
    :type cutoff_frequency: float or list[float]
    :param filter_type: The type of filter to apply. Options are "lowpass", "highpass", "bandpass", or "bandstop".
    :type filter_type: Literal["lowpass", "highpass", "bandpass", "bandstop"]
    :param filter_method: The filter method. Supported options: "butter" (Butterworth), "bessel". Defaults to "butter".
    :type filter_method: Literal["butter", "bessel"]
    :param order: The order of the filter. Must be >= 1. Defaults to 2.
    :type order: int
    :param bidirectional: If True, applies filtering forward and backward using `sosfiltfilt`.
                          If False, uses causal `sosfilt`. Defaults to True.
    :type bidirectional: bool
    :param sampling_frequency: Sampling frequency of the signal in Hz.
    :type sampling_frequency: float, optional

    """
    cutoff_frequency: float
    filter_type: Literal["lowpass", "highpass", "bandpass", "bandstop"]
    filter_method: Literal["butter", "bessel"] = field(default="butter")
    # order: int = field(default=2,min=1,max=16)
    bidirectional: bool = True
    sampling_frequency: float = None

    def __post_init__(self):
        if self.order < 1:
            self.order = 1

        if self.sampling_frequency:
            self._calculate_sos()

    def _calculate_sos(self):
        nyquist = 0.5 * self.sampling_frequency
        normalized_cutoff = self.cutoff_frequency / nyquist

        if self.filter_method == "butter":
            self.sos = signal.butter(self.order, normalized_cutoff,
                                     btype=self.filter_type,
                                     output='sos')
        elif self.filter_method == "bessel":
            self.sos = signal.bessel(self.order, normalized_cutoff,
                                     btype=self.filter_type,
                                     output='sos', norm='mag')
        else:
            raise ValueError(f"Unsupported filter method: {self.filter_method}")

    def __call__(self, current, sampling_frequency=None):
        if self.sampling_frequency is None and sampling_frequency is None:
            raise ValueError("Sampling frequency must be provided.")

        if sampling_frequency:
            self.sampling_frequency = sampling_frequency

        if not hasattr(self, 'sos'):
            self._calculate_sos()

        if self.bidirectional:
            current[:] = signal.sosfiltfilt(self.sos, current, axis=0)
        else:
            current[:] = signal.sosfilt(self.sos, current, axis=0)




@dataclass
class Trimmer:
    """
    Segment trimming utility for hierarchical signal data.

    This class operates on a segment tree. It traverses segments of a given rank (e.g., "vstep") and trims
    a fixed number of samples from the start of each segment. The resulting trimmed segments are added
    as new child segments with a specified new rank (e.g., "vstepgap").

    This is useful when initial samples of each segment include artifacts that should be excluded from analysis.

    :param samples_to_remove: Number of samples to trim from the beginning of each segment.
    :type samples_to_remove: int
    :param rank: The hierarchical rank of segments to target for trimming. Defaults to "vstep".
    :type rank: str
    :param newrank: The rank name to assign to newly created trimmed child segments. Defaults to "vstepgap".
    :type newrank: str
    """
    samples_to_remove: int
    rank: str = "vstep"
    newrank: str = "vstepgap"

    def __call__(self, trace_file):
        """
        Trim segments within 'vstep' and create 'vstepgap' children.
        """
        for v in trace_file.traverse_to_rank(self.rank):
            if v.end - v.start > self.samples_to_remove:
                v.add_child(MetaSegment(
                    start=v.start + self.samples_to_remove,
                    end=v.end,
                    rank=self.newrank,
                    parent=v
                ))
    # @classmethod
    # def via_GUI():
    #     pass
    #

def extract_features(seg, bottom_rank, extractions: list[str], add_ons: dict = {}, lambdas={}):
    """
    Extract features from hierarchical segments into a DataFrame.

    Traverses a hierarchical segment structure down to `bottom_rank`, then collects feature values
    from each segment. Static features are retrieved via `get_feature()`, constants can be added via
    `add_ons`, and custom computed features can be provided through `lambdas`.

    This is useful for generating structured datasets from annotated traces for statistical analysis or
    machine learning.

    :param seg: The root segment or trace object containing a hierarchical structure. It must implement `traverse_to_rank()` and support `get_feature()`.
    :type seg: object
    :param bottom_rank: The rank name of the lowest-level segments from which to extract features.
    :type bottom_rank: str
    :param extractions: List of feature names to extract directly using `get_feature()` on each segment.
                        Common examples include: 'mean', 'frac', 'duration', 'baseline', 'current', 'wrap', 'start'.
    :type extractions: list[str]
    :param add_ons: A dictionary of fixed key-value pairs to include as constant columns in the resulting DataFrame.
    :type add_ons: dict
    :param lambdas: A dictionary mapping column names to lambda functions that compute derived values from each segment.
    :type lambdas: dict
    :return: A pandas DataFrame where each row corresponds to a bottom-rank segment and columns represent extracted and computed features.
    :rtype: pandas.DataFrame
    """
    headers = extractions + list(add_ons.keys()) + list(lambdas.keys())

    df = pd.DataFrame(columns=headers)
    for bottom_seg in seg.traverse_to_rank(bottom_rank):
        row_dict = {}
        for feature in extractions:
            row_dict[feature] = bottom_seg.get_feature(feature)
        for feature, value in add_ons.items():
            row_dict[feature] = value
        for feature, lambda_func in lambdas.items():
            row_dict[feature] = lambda_func(bottom_seg)
        df.loc[len(df)] = row_dict
    return df
# extract_features(seg, bottom_rank='event',
#              extractions=['mean', 'frac', 'duration', 'baseline', 'current', 'wrap', 'start'],
#              add_ons={"sample_type": "MBP_D10"},
#              lambdas={"Voltage": lambda seg: int(1000 * seg.get_feature("voltage")),
#                       "start_time": lambda seg: seg.start / seg.get_feature("eff_sampling_freq")})



