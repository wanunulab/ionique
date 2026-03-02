ionique.utils
=============

The ``utils`` module provides preprocessing tools, feature extraction, and
helper utilities.

**Preprocessing:**

- ``Filter`` — frequency-domain filtering (lowpass, highpass, bandpass, bandstop)
- ``ClockFilter`` — clock-tone removal via sine-wave subtraction
- ``Trimmer`` — removes edge samples from segments at a given rank

**Feature extraction:**

- ``extract_features()`` — collects segment statistics into a pandas DataFrame

**Helpers:**

- ``split_voltage_steps()`` — detects voltage transitions and returns boundaries
- ``si_eval()`` — parses SI-prefixed value strings (e.g. ``"1.5 mV"`` → ``0.0015``)
- ``Singleton`` — metaclass for singleton pattern
- ``ignored()`` — context manager to suppress specific exceptions

See :doc:`/signal_preprocess` and :doc:`/signal_analysis` for usage examples.

.. automodule:: ionique.utils
   :members:
   :undoc-members:
   :show-inheritance:
