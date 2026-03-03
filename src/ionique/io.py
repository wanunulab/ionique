#!/usr/bin/env python
"""
Input/output utilities for data files.

This module provides an interface for loading, parsing, and preprocessing
signal data from various file formats (e.g., `.edh`, `.opt`, `.abf`, `.dat`, `.xml`). It defines a base reader class
and concrete implementations that handle format-specific logic, metadata extraction,
data alignment, and optional preprocessing steps.

This module is central to converting raw experimental data into analyzable form.
"""
import xml.etree.ElementTree as ET
import os
import glob
import pyabf
import numpy as np
from ionique.utils import si_eval
from ionique.utils import split_voltage_steps
from ionique.datatypes import SessionFileManager
import uuid
from scipy.signal import find_peaks

# from ionique.setup_log import json_logger

supported_extensions=[".opt",".edh"]


# try:
#     import cupy
#     from cupyx.scipy.signal import find_peaks
#     if not cupy.cuda.is_available():
#         raise ImportError
#     np = cupy
# except ImportError:
#     import numpy as np
#     from scipy.signal import find_peaks

class AbstractFileReader(object):
    """
    An abstract class for reading various data files (.abf, .edh, .mat, .opt, .xml)
    This class defines the structure for file readers
    """
    # File extension. Replace with the appropriate file extension
    # in subclass, such as ".abf", ".edh", ".mat", etc.
    ext = "___"

    # Replace with a list of accepted keyword arguments passed
    # to the _read() function in every subclass.
    accepted_keywords = []

    # Values to scale voltage and current to SI units.
    # Change these in subclasses to match the idata scale
    current_multiplier: float = 1.0
    voltage_multiplier: float = 1.0

    def __init__(self):
        self.filename = "UNDEFINED"
        self.uuid = str(uuid.uuid4())
        sfm = SessionFileManager()
        sfm.register_affector(self)
    def __repr__(self):
        return f"<AbstractFileReader UUID = {self.uuid}"

    def read(self, filename: str, **kwargs):
        """
        Read a datafile or series of files, identified by their extension.

        Data formats that come with a header file must be referred to by the header
        file. If inheriting from AbstractFileReader, do not override this method;
        instead, create a custom ``_read`` method.

        Parameters
        ----------
        filename : str or os.PathLike or list[str] or list[os.PathLike]
            File name or list of file names.
        **kwargs
            Keyword arguments passed directly to the format-specific ``_read`` method.

        Returns
        -------
        tuple[dict, np.ndarray, np.ndarray or list[tuple[slice, np.float32]]]
            A tuple of ``(metadata, current, voltage)``. If ``filename`` is a list,
            returns a generator that yields the output of ``_read()`` for each file.
        """
        for key in kwargs.keys():
            if key not in self.accepted_keywords:
                raise TypeError(f"{self.__class__}.read() got an unexpected argument: {key}")
        if type(filename) is list:
            self.kwargs = kwargs
            for fname in filename:
                assert os.path.splitext(fname)[-1].lower() == self.ext.lower()
            return (self._read(fname, **kwargs) for fname in filename)

        else:
            assert(os.path.splitext(filename)[-1].lower() == self.ext.lower())
            self.kwargs = kwargs
            return self._read(filename, **kwargs)

    def _read(self, filename, **kwargs):
        """Override in subclasses to implement format-specific file reading."""
        pass  # rewrite this function in inherited classes to process the data

    def __repr__(self):
        self.filename


class EDHReader(AbstractFileReader):
    """
    Reader class for loading `.edh` data files and their associated current data.

    This class parses the `.edh` header file and automatically loads the corresponding signal data
    (either from `.abf` or `.dat` files in the same directory). It extracts metadata, converts raw
    current and voltage data to SI units, and supports optional preprocessing steps such as
    voltage step segmentation, downsampling, and signal filtering.
    """

    ext = ".edh"
    accepted_keywords = ["voltage_compress", "n_remove", "downsample", "prefilter"]

    current_multiplier = 1e-9  # current is stored in nA in the datafile
    voltage_multiplier = 1e-3  # voltage is stored in mV in the datafile

    # @json_logger.log
    def __init__(self, edh_filename, voltage_compress=False, n_remove=0, downsample=1, prefilter=None):
        """
        Initialize the EDHReader and load signal data from associated files.

        Parameters
        ----------
        edh_filename : str
            Path to the `.edh` header file.
        voltage_compress : bool, optional
            If True, splits signal into segments based on voltage steps. Defaults to False.
        n_remove : int, optional
            Number of samples to remove from the beginning of each voltage step. Defaults to 0.
        downsample : int, optional
            Downsampling factor to reduce data size. Defaults to 1.
        prefilter : callable or None, optional
            Callable to apply preprocessing to the current signal. Defaults to None.
        """
        super().__init__()
        self.filename = edh_filename
        self.voltage_compress = voltage_compress
        self.n_remove = n_remove
        self.downsample = downsample
        self.prefilter = prefilter
        self.metadata, self.current, self.voltage = self._read()

    def __iter__(self):
        return iter((self.metadata, self.current, self.voltage))

    def _read(self):
        """
        Parse the `.edh` header and load associated signal data files.

        Returns
        -------
        tuple[dict, np.ndarray, np.ndarray or list[tuple[tuple[int, int], np.float32]]]
            A tuple of ``(metadata, current, voltage)``. ``metadata`` is a dict of
            header fields. ``current`` and ``voltage`` are float32 arrays scaled to
            SI units. If ``voltage_compress`` is True, ``voltage`` is replaced by a
            list of ``((start, stop), voltage_value)`` tuples for each voltage step.
        """
        filename = os.path.abspath(self.filename)

        direc = os.path.dirname(filename)
        metadata = {}

        with open(filename, 'r') as headerfile:
            for line in headerfile:
                lsplit = line.split(":")
                match lsplit:
                    case ["EDH Version" | "Channels" | "Oversampling x4" | "Active channels", *val]:
                        metadata[lsplit[0]] = "".join(val).strip()
                    case ["Sampling frequency (SR)" | "Range", *val]:
                        metadata[lsplit[0]] = si_eval("".join(val).strip())
                    case ["Final Bandwidth", *val]:
                        metadata["Final Bandwidth"] = metadata["Sampling frequency (SR)"] / \
                                                      int(val[0].strip().split()[0].split("/")[1])
                    case ["Acquisition start time", *val]:
                        metadata["Acquisition start time"] = " ".join(line.split(" ")[-2:])
                    case _:
                        pass

        file_list_abf = glob.glob("*.abf", root_dir=direc)

        if len(file_list_abf) > 0:
            abf_buffers = tuple(map(pyabf.ABF, [os.path.join(direc, file)
                                                for file in file_list_abf]))
            # list(map())
            current = np.concatenate([buffer.data[0] for buffer in abf_buffers],
                                     axis=0, dtype=np.float32)
            voltage = np.concatenate([buffer.data[-1] for buffer in abf_buffers],
                                     axis=0, dtype=np.float32)
            metadata["DataFiles"] = file_list_abf
            metadata["StorageFormat"] = ".abf"
        else:
            file_list_dat = glob.glob("*.dat", root_dir=direc)
            if len(file_list_dat) == 0:
                raise FileExistsError("No associated data files (*.abf or *.dat) found.")
            data = np.concatenate([np.fromfile(os.path.join(direc, file), dtype="float32")
                                   for file in file_list_dat])
            data = data.reshape((int(metadata["Active channels"])+1, -1), order="F")
            current = data[0]
            voltage = data[-1]
            metadata["DataFiles"] = file_list_dat
            metadata["StorageFormat"] = ".dat"
        assert current.shape == voltage.shape
        metadata["HeaderFile"] = filename

        if self.prefilter:
            assert callable(self.prefilter)
            self.prefilter(current)

        current *= self.current_multiplier
        voltage *= self.voltage_multiplier

        if self.downsample > 1:
            current_data = current[::self.downsample]
            voltage_data = voltage[::self.downsample]
        metadata["downsample"] = self.downsample
        metadata["eff_sampling_freq"] = metadata["Sampling frequency (SR)"] / self.downsample

        if self.voltage_compress:
            voltage_splits = split_voltage_steps(voltage, as_tuples=True, n_remove=self.n_remove)
            voltage_points = [(sl, voltage[sl[0]]) for sl in voltage_splits]
            del voltage
            return metadata, current, voltage_points

        return metadata, current, voltage


class OPTReader(AbstractFileReader):
    """
    Reader for `.opt` data files with corresponding XML or `_volt.opt` metadata.

    This class reads current data from `.opt` files and attempts to extract or reconstruct
    corresponding voltage data using associated `.xml` or `_volt.opt` files found in the same
    directory. It handles metadata extraction, signal preprocessing, voltage alignment, and
    segment compression based on voltage steps.

    Supported XML structures include both standard `HWtiming_cap_step` formats and timestamp-based
    custom formats.
    """

    ext = ".opt"
    accepted_keywords = ["voltage_compress", "n_remove", "downsample", "prefilter"]
    current_multiplier = 1e9  # Convert current to nA

    #@json_logger.log
    def __init__(self, opt_filename: str, voltage_compress=False, n_remove=0, downsample=1, prefilter=None):
        """
        Initialize the OPTReader instance and load corresponding files.

        Parameters
        ----------
        opt_filename : str
            Path to the `.opt` data file.
        voltage_compress : bool, optional
            If True, splits signal into segments based on voltage steps. Defaults to False.
        n_remove : int, optional
            Number of samples to remove from the beginning of each voltage step. Defaults to 0.
        downsample : int, optional
            Downsampling factor to reduce data size. Defaults to 1.
        prefilter : callable or None, optional
            Callable to apply preprocessing to the current signal. Defaults to None.
        """
        super().__init__()
        self.opt_filename = opt_filename
        self.voltage_compress = voltage_compress
        self.n_remove = n_remove
        self.downsample = downsample
        self.prefilter = prefilter
        self.sampling_frequency = 250000  # Default sampling frequency

        # Find xml or opt format file with voltage
        base_name = os.path.splitext(os.path.basename(opt_filename))[0]
        direc = os.path.dirname(opt_filename)

        pattern_xml = os.path.join(direc, f"{base_name}.xml")
        xml_file = glob.glob(pattern_xml)

        pattern_opt = os.path.join(direc, f"{base_name}_volt.opt")
        opt_file = glob.glob(pattern_opt)

        if opt_file:
            self.volt_filename = opt_file[0]
        elif xml_file:
            self.xml_filename = xml_file[0]

        else:
            raise FileNotFoundError(
                f"Neither a '_volt.opt' nor a '.xml' file was found")
        self.metadata, self.current, self.voltage = self._read()

    def __iter__(self):
        return iter((self.metadata, self.current, self.voltage))

    def _load_voltage_opt_file(self):
        """
        Load and denoise voltage data from the associated ``_volt.opt`` file.

        The recorded voltage is noisy and typically off by less than 1 mV.
        Noise is removed by rounding to the nearest 5 mV step, which is
        necessary for accurate voltage-current alignment.

        Returns
        -------
        np.ndarray
            Voltage array rounded to the nearest 5 mV step.
        """
        volt = np.fromfile(self.volt_filename, dtype='>d')
        voltage = np.round(volt / 5, decimals=3) * 5
        return voltage

    def _pre_check_xml(self, root):
        """
        Analyze the XML structure to determine the presence of key tags and attributes.

        Parameters
        ----------
        root : xml.etree.ElementTree.Element
            Root element of the parsed XML tree.

        Returns
        -------
        dict
            Dictionary with boolean values indicating the presence of specific XML
            elements: ``HWtiming_cap_step``, ``cap_step_waveform``, and ``timestamps``.
        """
        detected_features = {
            "HWtiming_cap_step": root.find(".//HWtiming_cap_step") is not None,
            "cap_step_waveform": root.find(".//HWtiming_cap_step/cap_step_waveform") is not None,
            "timestamps": len(root.findall(".//timestamp")) > 0
        }
        return detected_features

    def _read(self):
        """
        Load current and voltage data from the `.opt` file and associated metadata source.

        Returns
        -------
        tuple[dict, np.ndarray, np.ndarray or list[tuple[tuple[int, int], np.float32]]]
            A tuple of ``(metadata, current, voltage)``. ``metadata`` is a dict of
            experiment parameters. ``current`` and ``voltage`` are float32 arrays
            scaled to SI units. If ``voltage_compress`` is True, ``voltage`` is
            replaced by a list of ``((start, stop), voltage_value)`` tuples.
        """
        # if Voltage stored in `_volt.opt`
        if hasattr(self, 'volt_filename'):
            voltage = self._load_voltage_opt_file()
            metadata = {
                "HeaderFile": os.path.abspath(self.opt_filename),
                "Sampling frequency (SR)": self.sampling_frequency,
                 "total_samples": len(voltage)
            }

            current = self._load_opt_data()
        else:
            # Parse the XML
            try:
                tree = ET.parse(self.xml_filename)
                root = tree.getroot()
            except (FileNotFoundError, ET.ParseError) as e:
                raise IOError(f"Error reading XML file {self.xml_filename}: {e}")

            # Perform pre-check on XML structure
            features = self._pre_check_xml(root)

            try:
                # If HWtiming_cap_step exists, use standard parsing
                if features["HWtiming_cap_step"]:
                    metadata = self._parse_xml_metadata(root)
                    current = self._load_opt_data()
                    voltage = self._align_voltage(metadata, current)

                # custom XML processing
                elif features["timestamps"]:
                    voltage, time_points, sampling_frequency = self.process_custom_xml()
                    metadata = {
                        "Sampling frequency (SR)": sampling_frequency,
                        "total_samples": len(voltage),
                        "HeaderFile": os.path.abspath(self.xml_filename)
                    }
                    current = self._load_opt_data()
                else:
                    raise ValueError("Unsupported XML structure. No recognized features found.")
            except Exception as e:
                raise RuntimeError(f"Error processing XML file {self.xml_filename}: {e}")

        current *= self.current_multiplier

        # Post-processing
        if self.prefilter:
            assert callable(self.prefilter)
            self.prefilter(current)

        if voltage is not None:
            voltage *= self.voltage_multiplier

        if self.downsample > 1:
            current = current[::self.downsample]
            voltage = voltage[::self.downsample]
        metadata["downsample"] = self.downsample
        metadata["eff_sampling_freq"] = metadata["Sampling frequency (SR)"] / self.downsample

        if self.voltage_compress and voltage is not None:
            voltage_splits = split_voltage_steps(voltage, as_tuples=True, n_remove=self.n_remove)
            voltage_points = [(sl, voltage[sl[0]]) for sl in voltage_splits]
            del voltage
            return metadata, current, voltage_points

        return metadata, current, voltage

    def process_custom_xml(self):
        """
        Process a custom timestamp-based XML file to reconstruct the voltage waveform.

        Extracts voltage data and time points from ``<timestamp>`` elements, then
        aligns the reconstructed voltage waveform with the current signal by detecting
        capacitive peaks at each voltage transition.

        Returns
        -------
        tuple[np.ndarray, list[float], int]
            A tuple of ``(voltage_waveform, time_points, sampling_frequency)``.
            ``voltage_waveform`` is a float32 array aligned to the current signal.
            ``time_points`` is a list of transition times in seconds.
            ``sampling_frequency`` is the sample rate in Hz.
        """
        sampling_frequency = 250000
        current = self._load_opt_data()
        try:
            tree = ET.parse(self.xml_filename)
            root = tree.getroot()
        except (FileNotFoundError, ET.ParseError) as e:
            raise IOError(f"Error reading XML file {self.xml_filename}: {e}")

        voltage_data = []
        time_points = []
        timestamps = root.findall(".//timestamp")

        # Extract timestamps and voltages
        for timestamp in timestamps:
            msec = timestamp.get("msec")
            voltage = timestamp.find("voltage")

            if msec is not None and voltage is not None:
                try:
                    time = float(msec) / 1000  # Convert milliseconds to seconds
                    volt_value = float(voltage.get("volt")) / 1000.0
                    # volt_value = float(voltage.get("volt"))
                    time_points.append(time)
                    voltage_data.append((time, volt_value))
                except ValueError as e:
                    raise ValueError(f"Invalid timestamp in XML: {e}")

        if not time_points:
            raise ValueError(f"No time points found in {self.xml_filename}")

        total_samples = int(round(time_points[-1] * sampling_frequency))
        voltage_waveform = np.ones(len(current), dtype=np.float32)
        initial_voltage = float(root.find(".//inital_UI_voltage").get("volt")) / 1000.0
        # initial_voltage = float(root.find(".//inital_UI_voltage").get("volt"))
        voltage_waveform *= initial_voltage

        # Find peaks for each segment
        starts, ends, volt_values = [], [], []

        for i in range(len(voltage_data)-1):
            starts.append(voltage_data[i][0])
            ends.append(voltage_data[i + 1][0])
            volt_values.append(voltage_data[i][1])
        starts.append(ends[-1])
        volt_values.append(voltage_data[-1][1])
        ends.append(len(current))

        prev_voltage = voltage_waveform[0]
        global_alignment = None
        window_shift_duration = 0.08 #80ms
        for start_time,end_time,volt_value in zip(starts,ends,volt_values):
            volt_difference=volt_value-prev_voltage
            # approximate start_sample
            approximate_start_sample = int(round(start_time * sampling_frequency))
            end_sample = int(round(end_time * sampling_frequency))

            # get exact index of the first peak in the +/- 2 ms window
            if volt_difference > 0:
                exact_start_index = self.find_peaks_slide_window(current, approximate_start_sample,window_shift_duration,
                                                                 sampling_frequency=sampling_frequency,sign="positive")
            else:
                exact_start_index = self.find_peaks_slide_window(current, approximate_start_sample,window_shift_duration,
                                                                 sampling_frequency=sampling_frequency, sign="negative")

            # If no peak is found, fallback to approximate start sample
            if exact_start_index is None:
                exact_start_index = approximate_start_sample

            # voltage to waveform from exact start index to end sample
            shift_samples=exact_start_index-approximate_start_sample
            # if exact_start_index < end_sample-shift_samples:
            window_shift=int(0.02 * sampling_frequency)
            voltage_waveform[exact_start_index:min(end_sample+window_shift,len(voltage_waveform))] = volt_value
            if global_alignment is None:
                for i in range(1,len(starts)):
                    starts[i] += shift_samples/sampling_frequency
                    ends[i]+=shift_samples/sampling_frequency
                global_alignment=True
                window_shift_duration=0.002
            # break
            # else:
            #     print(
            #         f"Skipping voltage assignment for volt_value={volt_value} because "
            #         f"exact_start_index={exact_start_index} is not less than end_sample={end_sample}")

            # previous_end_sample = end_sample
            prev_voltage=volt_value

        return voltage_waveform, time_points, sampling_frequency

    def find_peaks_slide_window(self, current, start_index,window_shift_duration=0.002, sampling_frequency=250000, sign="negative"):
        """
        Find the first capacitive peak near a voltage transition in the current signal.

        Searches a symmetric window of half-width ``window_shift_duration`` seconds
        around ``start_index`` for a positive or negative peak, and returns the
        left edge of the first detected peak.

        Parameters
        ----------
        current : np.ndarray
            Full ionic current signal array.
        start_index : int
            Approximate sample index of the voltage transition.
        window_shift_duration : float, optional
            Half-width of the search window in seconds. Defaults to 0.002.
        sampling_frequency : int, optional
            Sampling rate in Hz. Defaults to 250000.
        sign : str, optional
            Direction of the peak to search for: ``"negative"`` or ``"positive"``.
            Defaults to ``"negative"``.

        Returns
        -------
        int or None
            Sample index of the left edge of the first detected peak, or ``None``
            if no peak was found within the window.
        """
        window_shift = int(window_shift_duration * sampling_frequency)
        start_window = max(0, start_index - window_shift)
        end_window = min(len(current), start_index + window_shift)

        #  segment of the current
        segment = current[start_window:end_window]
        # change to the diff

        if sign == "negative":
            peaks, properties = find_peaks(-segment, height=1e-9,prominence=1e-9,plateau_size=[None,None])
        else:
            peaks, properties = find_peaks(segment, height=1e-9,prominence=1e-9,plateau_size=[None,None])

        if len(peaks) > 0:
            # exact_start_index = peaks[0] + start_window
            exact_start_index = properties['left_edges'][0] + start_window-1

            return exact_start_index
        else:
            return None

    def _parse_xml_metadata(self, root):
        """
        Parse the XML file and extract experiment metadata, handling missing elements gracefully.

        Parameters
        ----------
        root : xml.etree.ElementTree.Element
            Root element of the parsed XML tree.

        Returns
        -------
        dict
            Metadata dictionary containing sampling info, acquisition time, and file info.
            Missing fields are filled with default values and a warning is printed.
        """
        metadata = {"HeaderFile": os.path.abspath(self.xml_filename)}

        try:
            metadata.update(self._extract_sampling_info(root))
        except ValueError as e:
            metadata["Sampling frequency (SR)"] = 250000
            metadata["total_samples"] = None
            metadata["total_time_s"] = None
            print(f"Warning: Missing sampling info. Using default values. {e}")

        try:
            metadata.update(self._extract_acquisition_time(root))
        except ValueError as e:
            metadata["Acquisition start time"] = "Unknown"
            print(f"Warning: Missing acquisition time. {e}")

        metadata.update(self._extract_file_info())
        return metadata

    def _extract_sampling_info(self, root):
        """
        Extract sampling frequency, total samples, and total recording time from the XML.

        Parameters
        ----------
        root : xml.etree.ElementTree.Element
            Root element of the parsed XML tree.

        Returns
        -------
        dict
            Dictionary with keys ``"Sampling frequency (SR)"`` (float, Hz),
            ``"total_samples"`` (int), and ``"total_time_s"`` (float, seconds).

        Raises
        ------
        ValueError
            If ``HWtiming_cap_step`` or ``cap_step_waveform`` elements are absent.
        """
        hw_timing = root.find(".//HWtiming_cap_step")
        hw_timing_1 = hw_timing.find("cap_step_waveform")

        if hw_timing is None or hw_timing_1 is None:
            raise ValueError("HWtiming_cap_step or cap_step_waveform not found in XML.")

        sample_rate = float(hw_timing.get("sample_rate_Hz"))
        total_samples = int(hw_timing_1.get("number_samples"))
        total_time = total_samples / sample_rate

        return {
            "Sampling frequency (SR)": sample_rate,
            "total_samples": total_samples,
            "total_time_s": total_time}

    def _extract_acquisition_time(self, root):
        """
        Get acquisition start time from the XML.

        Parameters
        ----------
        root : xml.etree.ElementTree.Element
            Root element of the parsed XML tree.

        Returns
        -------
        dict
            Dictionary with key ``"Acquisition start time"`` (str) if the
            ``wall_clock`` attribute is found on the first ``<timestamp>`` element,
            otherwise an empty dict.
        """
        start_time = root.find(".//timestamp")
        if start_time is not None and "wall_clock" in start_time.attrib:
            return {"Acquisition start time": start_time.attrib["wall_clock"]}
        return {}

    def _extract_file_info(self):
        """
        Get filename and storage format metadata from the XML file path.

        Returns
        -------
        dict
            Dictionary with keys ``"DataFiles"`` (list[str]) and
            ``"StorageFormat"`` (str, the file extension).
        """
        return {
            "DataFiles": [os.path.basename(self.xml_filename)],
            "StorageFormat": os.path.splitext(self.xml_filename)[-1]}

    def _calculate_bandwidth(self, metadata):
        """
        Calculate the final acquisition bandwidth from the sampling frequency.

        Parameters
        ----------
        metadata : dict
            Metadata dictionary containing ``"Sampling frequency (SR)"`` (float, Hz).

        Returns
        -------
        dict
            Dictionary with key ``"Final Bandwidth"`` (float, Hz). Returns half the
            sampling frequency for rates below 200 kHz, otherwise 100 kHz.
        """
        sampling_frequency = metadata["Sampling frequency (SR)"]
        return {"Final Bandwidth": sampling_frequency / 2 if sampling_frequency < 200000 else 100000}

    def _load_opt_data(self):
        """
        Read raw current data from the `.opt` binary file.

        Returns
        -------
        np.ndarray
            1-D array of current values in big-endian double format (``">d"``),
            prior to unit conversion.

        Raises
        ------
        IOError
            If the file cannot be read.
        """
        try:
            dtype = np.dtype(">d")
            current = np.fromfile(self.opt_filename, dtype)
            return current
        except Exception as e:
            raise IOError(f"Error reading OPT file {self.opt_filename}: {e}")

    def _align_voltage(self, metadata, current_full):
        """
        Align the voltage waveform to the current signal using XML metadata.

        Reconstructs the voltage array from XML time-alignment marks and cap-step
        waveform data, anchoring it to the first capacitive peak detected in the
        current signal.

        Parameters
        ----------
        metadata : dict
            Metadata dictionary containing ``"total_samples"`` (int) and
            ``"Sampling frequency (SR)"`` (float, Hz).
        current_full : np.ndarray
            Full ionic current signal array (unscaled).

        Returns
        -------
        np.ndarray
            Float32 voltage waveform array, same length as ``current_full``,
            with values in millivolts.

        Raises
        ------
        ValueError
            If time alignment marks are missing or no alignment peak is detected.
        """
        if not hasattr(self, "_xml_tree"):
            self._xml_tree = ET.parse(self.xml_filename).getroot()
        root = self._xml_tree
        total_samples = metadata["total_samples"]
        sample_rate = metadata["Sampling frequency (SR)"]

        # Calculate the initial start sample
        start_sample = self._get_start_sample(root, sample_rate)

        # Initialize voltage array
        voltage_waveform = np.zeros(len(current_full), dtype=np.float32)

        # TODO: Remove an error. Not all the files will have this tag
        time_marks = root.find(".//HWtiming_cap_step/time_alignment_marks")
        if time_marks is None:
            raise ValueError("Time alignment marks not found in the XML.")

        # TODO: Should we change to a certain value the end limit of the find_peak search?
        search_end = len(current_full)

        # Detect the first peak in the segment
        peaks, properties = self.find_peaks_in_segment(current_full, start_sample, search_end)

        if not peaks.size:
            raise ValueError("No peaks detected in the current data for alignment.")

        first_peak_index = peaks[0] + start_sample

        # Process time alignment marks, adjusting for zero-voltage samples
        current_index = self._process_time_marks(root, voltage_waveform, first_peak_index)

        # Process cap step waveform
        self._process_cap_step_waveform(root, voltage_waveform, current_index)

        return voltage_waveform

    def _get_start_sample(self, root, sample_rate):
        """
        Retrieve the starting sample index from the last pre-acquisition timestamp.

        Parameters
        ----------
        root : xml.etree.ElementTree.Element
            Root element of the parsed XML tree.
        sample_rate : float
            Sampling frequency in Hz.

        Returns
        -------
        int
            Sample index corresponding to the last ``<timestamp msec=...>`` element
            found before the ``<HWtiming_cap_step>`` element.

        Raises
        ------
        ValueError
            If no ``<timestamp>`` element with a ``msec`` attribute is found.
        """
        last_msec = None
        for elem in root.iter():
            if elem.tag == "timestamp" and "msec" in elem.attrib:
                last_msec = float(elem.attrib["msec"])
            elif elem.tag == "HWtiming_cap_step":
                break

        if last_msec is None:
            raise ValueError("No <timestamp> with 'msec' attribute found.")
        msec = int(last_msec * sample_rate / 1000)

        return msec

    def _process_time_marks(self, root, voltage_waveform, first_peak_index):
        """
        Fill the voltage waveform array using XML time-alignment segment data.

        Fills ``voltage_waveform`` in-place starting from
        ``first_peak_index - zero_voltage_samples``, where ``zero_voltage_samples``
        is the number of leading zero-voltage samples in the alignment marks.

        Parameters
        ----------
        root : xml.etree.ElementTree.Element
            Root element of the parsed XML tree.
        voltage_waveform : np.ndarray
            Voltage array to fill in-place (float32, length matches current signal).
        first_peak_index : int
            Sample index of the first detected capacitive peak in the current signal.

        Returns
        -------
        int
            Sample index immediately after the last time-alignment segment written.
        """

        time_marks = root.find(".//HWtiming_cap_step/time_alignment_marks")
        zero_voltage_samples = 0
        total_samples_processed = 0
        if time_marks is not None:
            # get the samples before the first peak (zero voltage samples)
            for segment in time_marks.findall("time_alignment_segment"):
                number_samples = int(segment.get("number_samples"))
                voltage_mV = float(segment.get("voltage_mV"))

                if voltage_mV == 0.0:
                    zero_voltage_samples += number_samples
                else:
                    break

            # shift the starting idx
            start_index = max(first_peak_index - zero_voltage_samples, 0)

            # Now process all time alignment segments
            for segment in time_marks.findall("time_alignment_segment"):
                number_samples = int(segment.get("number_samples"))
                voltage_mv = float(segment.get("voltage_mV"))
                # Assign voltage values starting from the adjusted index
                voltage_waveform[start_index:start_index + number_samples] = voltage_mv
                start_index += number_samples
                total_samples_processed += number_samples

        return start_index

    def _process_cap_step_waveform(self, root, voltage_waveform, current_index):
        """
        Fill the voltage waveform array with capacitive triangle-wave step segments.

        Reads ``<triangle_wave>`` elements from ``<cap_step_waveform>`` in the XML
        and writes the corresponding voltage offset values into ``voltage_waveform``
        in-place, starting at ``current_index``.

        Parameters
        ----------
        root : xml.etree.ElementTree.Element
            Root element of the parsed XML tree.
        voltage_waveform : np.ndarray
            Voltage array to fill in-place (float32, length matches current signal).
        current_index : int
            Sample index at which to begin writing cap-step voltage values.

        Returns
        -------
        int or None
            Sample index immediately after the last cap-step segment written, or
            ``None`` if no ``<cap_step_waveform>`` element was found.
        """
        cap_waveform = root.find(".//HWtiming_cap_step/cap_step_waveform")
        if cap_waveform is None:
            return
        leading_samples = int(cap_waveform.get("leading_number_samples", 0))
        trailing_samples = int(cap_waveform.get("trailing_number_samples", 0))

        first_triangle = cap_waveform.find(".//triangle_wave")
        if first_triangle is not None:
            leading_offset = float(first_triangle.get("offset_mV"))
            voltage_waveform[current_index:current_index + leading_samples + trailing_samples] = leading_offset

        for triangle in cap_waveform.findall(".//triangle_wave"):
            offset_mV = float(triangle.get("offset_mV"))
            total_N_sample = int(triangle.get("total_N_sample"))
            end_index = current_index + total_N_sample + trailing_samples + leading_samples
            voltage_waveform[current_index:end_index] = offset_mV
            current_index = end_index

        return current_index

    def find_peaks_in_segment(self, current_data, start_index, end_index):
        """
        Apply ``scipy.signal.find_peaks`` on a slice of the current signal.

        Parameters
        ----------
        current_data : np.ndarray
            Full ionic current signal array.
        start_index : int
            Start index of the slice to search (inclusive).
        end_index : int
            End index of the slice to search (exclusive).

        Returns
        -------
        peaks : np.ndarray
            Indices of detected peaks relative to the start of the slice.
        properties : dict
            Properties dict returned by ``scipy.signal.find_peaks``.
        """
        # slice original data
        segment = current_data[start_index:end_index]

        peaks, properties = find_peaks(segment, height=1e-9)

        return peaks, properties



