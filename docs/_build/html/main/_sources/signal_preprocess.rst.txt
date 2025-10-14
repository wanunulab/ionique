Signal Preprocessing
====================

Signal preprocessing is an essential step before downstream analysis of nanopore signals.
It typically involves filtering, trimming, downsampling, or compressing signal segments
to reduce noise and improve performance.

This page describes the following functionalities of Ionique:

- Filtering: denoise signals.
- Trimming: remove edge artifacts from signal segments.

Filtering with `Filter` class
-----------------------------

The `Filter` class allows users to apply different types of filters on current traces:

**Supported filter types:**

- ``lowpass``: Passes low frequencies below a cutoff.
- ``highpass``: Passes high frequencies above a cutoff.
- ``bandpass``: Passes a frequency band between low and high cutoff.
- ``bandstop``: Removes a frequency band between low and high cutoff.


**Supported filter methods:**

- ``butter``: Butterworth filter (default) – smooth and flat frequency response.
- ``bessel``: Bessel filter – preserves waveform shape and group delay.

Filtering is applied using `scipy.signal.sosfiltfilt` (zero-phase, bidirectional) or
`scipy.signal.sosfilt` depending on `bidirectional=True/False`.


**Usage Example:**

.. code-block:: python

   filt = Filter(
       cutoff_frequency=[0.1, 10],
       filter_type="bandpass",
       filter_method="butter",
       order=3,
       bidirectional=True,
       sampling_frequency=10000
   )
   filt(current_trace)


Trimming with `Trimmer` class
-----------------------------

The `Trimmer` class removes a fixed number of samples from the start of each segment
at a given hierarchical rank (e.g., "vstep"). This is useful for excluding artifacts
 in step protocols.


**Usage Example:**

.. code-block:: python

   trimmer = Trimmer(samples_to_remove=200)
   trimmer(trace_file)


Summary
-------

Both `Filter` and `Trimmer` are designed to be composable tools for preprocessing current traces before
event detection and feature extraction. You can chain them together in the analysis workflows.


These operations are performed using tools in ``utils.py`` and parser modules