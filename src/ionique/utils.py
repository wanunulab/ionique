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
        Initialize the metaclass and set the singleton instance to None.

        Parameters
        ----------
        args : tuple
            Arguments for the class.
        kwargs : dict
            Keyword arguments for the class.
        """
        self.__instance = None
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        """
        Return the Singleton instance, creating it if it does not yet exist.

        If the instance exists, it is returned as-is.

        Parameters
        ----------
        args : tuple
            Arguments for the class constructor.
        kwargs : dict
            Keyword arguments for the class constructor.

        Returns
        -------
        object
            The Singleton instance.
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

    Parameters
    ----------
    voltage : numpy.ndarray
        1D voltage signal array to be segmented.
    n_remove : int, optional
        Number of samples to remove from the start of each split. Defaults to 0.
    as_tuples : bool, optional
        If True, returns a list of (start, end) index tuples. If False, returns
        two arrays: start_indices and end_indices. Defaults to False.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray] or list[tuple[int, int]]
        Either a tuple of (start_indices, end_indices) where each is a numpy
        array of indices, or a list of (start, end) tuples if `as_tuples=True`.

    Raises
    ------
    ValueError
        If `n_remove` is negative or larger than the start of the voltage changes.
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

    Parameters
    ----------
    value : str or float
        The value to be converted. Can be a string like "1.2 kHz" or a numeric
        value (int or float).
    unit : str, optional
        The unit string (e.g., "kHz", "mV"). Required only if `value` is a
        numeric type.
    return_unit : bool, optional
        If True, returns a tuple containing the converted numeric value and the
        base unit (e.g., 'Hz'). If False, only the numeric value is returned.

    Returns
    -------
    float or tuple[float, str]
        The converted value, optionally paired with the base unit.

    Raises
    ------
    ValueError
        If the input format is invalid or the unit is missing for numeric input.
    TypeError
        If the value is neither a string nor a numeric type.
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

    Returns
    -------
    dict
        A dictionary mapping SI prefixes to their multiplier values.
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

    Parameters
    ----------
    unitstr : str
        A single character string representing an SI prefix.

    Returns
    -------
    float
        The multiplier corresponding to the given SI prefix.
    """

    if unitstr in _get_prefix_val():
        return _get_prefix_val()[unitstr]

    raise ValueError(f"Unit prefix is not known: {unitstr}, see available:\n{_get_prefix_val()}")

@dataclass
class Filter:
    """
    Apply low-pass, high-pass, band-pass, or band-stop filters using SOS form.

    Filters are implemented using second-order sections (SOS) for numerical
    stability and can be applied in either forward-only or bidirectional mode.

    Parameters
    ----------
    cutoff_frequency : float or list[float]
        The cutoff frequency or frequency band for the filter in Hz. For band
        filters, provide a list of [low, high] values.
    filter_type : Literal["lowpass", "highpass", "bandpass", "bandstop"]
        The type of filter to apply.
    filter_method : Literal["butter", "bessel"], optional
        The filter design method. Supported options: "butter" (Butterworth) and
        "bessel". Defaults to "butter".
    order : int, optional
        The order of the filter. Must be >= 1. Defaults to 2.
    bidirectional : bool, optional
        If True, applies filtering forward and backward using `sosfiltfilt`.
        If False, uses causal `sosfilt`. Defaults to True.
    sampling_frequency : float, optional
        Sampling frequency of the signal in Hz.

    Attributes
    ----------
    sos : numpy.ndarray
        Second-order sections representation of the filter, computed after
        initialization when `sampling_frequency` is provided.
    """
    cutoff_frequency: float
    filter_type: Literal["lowpass", "highpass", "bandpass", "bandstop"]
    filter_method: Literal["butter", "bessel"] = field(default="butter")
    order: int = field(default=2,metadata={"min":1,"max":16})
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
        """
        Apply the filter to a signal array in-place.

        Parameters
        ----------
        current : numpy.ndarray
            The signal array to filter. Modified in-place.
        sampling_frequency : float, optional
            Sampling frequency in Hz. Overrides the instance attribute if
            provided. Required if not set at construction time.

        Returns
        -------
        None
            The array is modified in-place; nothing is returned.

        Raises
        ------
        ValueError
            If no sampling frequency is available from either the instance
            attribute or this argument.
        """
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
class ClockFilter:
    """
    Remove a single periodic clock frequency from a signal by sine-wave subtraction.

    If the power spectral density of a signal contains a very narrow and sharp
    peak at one frequency caused by EMF interference from a digital signal, this
    filter can eliminate its effect. Unlike a notch filter, it subtracts a
    phase-matching sine wave of the exact frequency from the signal. For multiple
    clock frequencies or harmonics, apply once per frequency. Can be used before,
    after, or without low-pass filtering.

    Parameters
    ----------
    clock_frequency : float
        Clock frequency to be removed, in Hz.
    section_length : float, optional
        Length of sections in seconds to use for noise estimation. Each section
        is filtered independently. Defaults to 0.5.
    sampling_frequency : float, optional
        Sampling frequency of the signal in Hz.
    """
    clock_frequency: float
    section_length: float = field(default=0.5, metadata={"min":0.000001}) #in seconds
    sampling_frequency: float = None
     
    

    def __call__(self, current, sampling_frequency=None):
        """
        Run the clock filter in-place in a memory-efficient way.

        Processes the signal in sections without duplicating the full array.

        Parameters
        ----------
        current : numpy.ndarray
            1D signal array to filter. Modified in-place.
        sampling_frequency : float, optional
            Sampling frequency in Hz. Overrides the instance attribute if
            provided. Required if not set at construction time.

        Returns
        -------
        None
            The array is modified in-place; nothing is returned.

        Raises
        ------
        ValueError
            If no sampling frequency is available from either the instance
            attribute or this argument, or if `current` is not 1D.
        """
        if self.sampling_frequency is None and sampling_frequency is None:
            raise ValueError("Sampling frequency must be provided.")

        if sampling_frequency is not None:
            self.sampling_frequency = float(sampling_frequency)

        fs = float(self.sampling_frequency)
        f0 = float(self.clock_frequency)

        if current.ndim != 1:
            raise ValueError("current must be a 1D array.")
        if current.size == 0:
            return

        from fractions import Fraction

        def find_period_samples(fs_: float, f0_: float,
                                rel_tol: float = 1e-12,
                                max_den: int = 10_000_000,
                                max_period: int = 1_000_000):
            """If f0/fs is (effectively) rational, return reduced denominator q (period in samples). Else None."""
            r = f0_ / fs_
            if not np.isfinite(r) or r == 0.0:
                return None
            frac = Fraction(r).limit_denominator(max_den)
            p, q = frac.numerator, frac.denominator
            if q <= 0 or q > max_period:
                return None
            if abs(r - (p / q)) <= rel_tol * max(1.0, abs(r)):
                return q
            return None

        def remove_tone_dot_inplace(x: np.ndarray, c_lut: np.ndarray, s_lut: np.ndarray):
            """
            Fast removal assuming len(x) is an integer multiple of len(c_lut).
            Uses reshape views (no tiling) and subtracts in-place.
            """
            N = x.size
            P = c_lut.size
            if N == 0:
                return
            if N % P != 0:
                return  # caller guarantees; if violated, do nothing

            X = x.reshape(-1, P)  # view
            xc = float(np.sum(X * c_lut))
            xs = float(np.sum(X * s_lut))
            a = (2.0 / N) * xc
            b = (2.0 / N) * xs

            tone_lut = a * c_lut + b * s_lut  # only P samples allocated
            X -= tone_lut  # broadcast subtract, in-place
            return a,b

        def remove_tone_by_fitting_inplace(x: np.ndarray, fs_: float, f0_: float):
            """
            2-parameter LS on the tail via 2x2 normal equations, no ridge regularization.
            """
            N = x.size
            if N < 2:
                return

            w0 = 2.0 * np.pi * f0_ / fs_
            n = np.arange(N, dtype=np.float64)
            c = np.cos(w0 * n)
            s = np.sin(w0 * n)

            X = np.column_stack((c, s))
            theta, *_ = np.linalg.lstsq(X, np.asarray(x), rcond=None)
            a, b = theta

            tone = a*c + b*s

            x -= tone

        # Section size in samples
        section_n_samples = int(round(fs * float(self.section_length)))
        section_n_samples = max(1, section_n_samples)

        # Find discrete-time period (if rational enough)
        n_period = find_period_samples(fs, f0)

        # Prepare LUT if usable
        use_fast = (n_period is not None) and (n_period > 0) and (n_period <= section_n_samples)
        if use_fast:
            w0 = 2.0 * np.pi * f0 / fs
            nL = np.arange(n_period, dtype=np.float64)
            c_lut = np.cos(w0 * nL)
            s_lut = np.sin(w0 * nL)
        else:
            n_period = None
            c_lut = s_lut = None

        # Internal robustness knob: if remainder is tiny, move one (or more) full periods into the tail
        min_fit = n_period*10

        # Process all sections, including final partial section
        for start in range(0, current.size, section_n_samples):
            stop = min(start + section_n_samples, current.size)
            seg_len = stop - start
            if seg_len <= 0:
                break

            if not use_fast or n_period is None or n_period <= 1:
                remove_tone_by_fitting_inplace(current[start:stop], fs, f0)
                continue

            rem = seg_len % n_period
            full_len = seg_len - rem

            # If remainder is too short, steal one (or more) full periods from the LUT part
            while rem != 0 and rem < min_fit and full_len >= n_period:
                full_len -= n_period
                rem += n_period

            mid = start + full_len
            dot_theta=None
            if full_len > 0:
                dot_theta=remove_tone_dot_inplace(current[start:mid], c_lut, s_lut)
                
                # remove_tone_by_fitting_inplace(current[start:stop],fs,f0)

            if mid < stop:
                if dot_theta is not None:
                    n=stop-mid
                    c = np.cos(w0*np.arange(n))
                    s = np.sin(w0*np.arange(n))
                    a,b=dot_theta
                    current[mid:stop]-= a*c+b*s
                else:
                    remove_tone_by_fitting_inplace(current[mid:stop], fs, f0)  
        return


@dataclass
class Trimmer:
    """
    Segment trimming utility for hierarchical signal data.

    Traverses segments of a given rank and trims a fixed number of samples from
    the start of each segment. The resulting trimmed segments are added as new
    child segments with a specified new rank. Useful when initial samples of each
    segment contain artifacts that should be excluded from analysis.

    Parameters
    ----------
    samples_to_remove : int
        Number of samples to trim from the beginning of each segment.
    rank : str, optional
        The hierarchical rank of segments to target for trimming.
        Defaults to "vstep".
    newrank : str, optional
        The rank name to assign to newly created trimmed child segments.
        Defaults to "vstepgap".
    """
    samples_to_remove: int
    rank: str = "vstep"
    newrank: str = "vstepgap"

    def __call__(self, trace_file):
        """
        Trim segments within the target rank and create child segments.

        Traverses all segments of `self.rank` in `trace_file` and, for each
        segment longer than `samples_to_remove`, adds a new child
        `MetaSegment` of rank `self.newrank` starting after the trimmed
        samples.

        Parameters
        ----------
        trace_file : object
            A segment tree object that implements `traverse_to_rank()` and
            `add_child()`.

        Returns
        -------
        None
            Child segments are added in-place to the tree; nothing is returned.
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

    Parameters
    ----------
    seg : object
        The root segment or trace object containing a hierarchical structure.
        Must implement `traverse_to_rank()` and support `get_feature()`.
    bottom_rank : str
        The rank name of the lowest-level segments from which to extract
        features.
    extractions : list[str]
        List of feature names to extract directly using `get_feature()` on
        each segment. Common examples include: 'mean', 'frac', 'duration',
        'baseline', 'current', 'wrap', 'start'.
    add_ons : dict, optional
        A dictionary of fixed key-value pairs to include as constant columns
        in the resulting DataFrame.
    lambdas : dict, optional
        A dictionary mapping column names to lambda functions that compute
        derived values from each segment.

    Returns
    -------
    pandas.DataFrame
        A DataFrame where each row corresponds to a bottom-rank segment and
        columns represent extracted and computed features.

    Examples
    --------
    >>> df = extract_features(
    ...     seg,
    ...     bottom_rank='event',
    ...     extractions=['mean', 'frac', 'duration', 'baseline', 'current', 'wrap', 'start'],
    ...     add_ons={"sample_type": "MBP_D10"},
    ...     lambdas={
    ...         "Voltage": lambda seg: int(1000 * seg.get_feature("voltage")),
    ...         "start_time": lambda seg: seg.start / seg.get_feature("eff_sampling_freq"),
    ...     },
    ... )
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


from contextlib import contextmanager
@contextmanager
def ignored(*exceptions):
    """
    Context manager that silently suppresses the specified exception types.

    Replaces the ``try/except: pass`` pattern with a single-line context manager.
    Taken from the Python 3.4 update by Raymond Hettinger; see:
    http://hg.python.org/cpython/rev/406b47c64480

    Parameters
    ----------
    *exceptions : type
        One or more exception classes to suppress within the ``with`` block.

    Yields
    ------
    None
        Control is yielded to the body of the ``with`` block; any listed
        exceptions raised within are silently caught and discarded.
    """
    try:
        yield
    except exceptions:
        pass