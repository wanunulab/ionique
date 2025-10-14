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
        Read a datafile or series of files. Files are identified according to their extension.
        Data formats that come with a header file must be referred to by the header file.
        If inheriting from the AbstractFileReader class, do not override this function;
        instead, create a custom _read method.

        :param filename: file name or list of file names, typically
        given as a string or PathLike object.
        :type filename: str or os.PathLike or list[str] or list[os.PathLike]
        :param **kwargs: keyword arguments passed directly to the file reader class
        that matches the data format.
        :return: [metadata, current, etc.. ]. If the input "filename" is a list,
        this function returns a generator
        object that yields the output of _read() for every file in the input list.
        :rtype: tuple[dict,np.ndarray [,np.ndarray or tuple[slice,np.float32]]]
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

        :param edh_filename: Path to the `.edh` header file.
        :type edh_filename: str
        :param voltage_compress: If True, splits signal into segments based on voltage steps.
        :type voltage_compress: bool
        :param n_remove: Number of samples to remove from the beginning of each voltage step.
        :type n_remove: int
        :param downsample: Downsampling factor to reduce data size.
        :type downsample: int
        :param prefilter: Callable to apply preprocessing to the current signal.
        :type prefilter: callable or None

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

        :param opt_filename: Path to the `.opt` header file.
        :type opt_filename: str
        :param voltage_compress: If True, splits signal into segments based on voltage steps.
        :type voltage_compress: bool
        :param n_remove: Number of samples to remove from the beginning of each voltage step.
        :type n_remove: int
        :param downsample: Downsampling factor to reduce data size.
        :type downsample: int
        :param prefilter: Callable to apply preprocessing to the current signal.
        :type prefilter: callable or None
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
        Load voltage data from _volt.opt file.
        The recorded voltage is noisy and typically off by <1 mV.
        Remove the noise in voltage data rounding it to the nearest 5mV step.
        This step is necessary for a better voltage-current alignment
        """
        volt = np.fromfile(self.volt_filename, dtype='>d')
        voltage = np.round(volt / 5, decimals=3) * 5
        return voltage

    def _pre_check_xml(self, root):
        """
        Analyzes the XML structure to determine the presence of key tags and attributes.
        Returns:
            - detected_features: Dict indicating the presence of specific XML elements.
        """
        detected_features = {
            "HWtiming_cap_step": root.find(".//HWtiming_cap_step") is not None,
            "cap_step_waveform": root.find(".//HWtiming_cap_step/cap_step_waveform") is not None,
            "timestamps": len(root.findall(".//timestamp")) > 0
        }
        return detected_features

    def _read(self):
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
        Processes the custom XML file to extract voltage data, align the voltage waveform
        with the current, and detect peaks in the current signal every time the voltage changes.
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
                    volt_value = float(voltage.get("volt"))
                    time_points.append(time)
                    voltage_data.append((time, volt_value))
                except ValueError as e:
                    raise ValueError(f"Invalid timestamp in XML: {e}")

        if not time_points:
            raise ValueError(f"No time points found in {self.xml_filename}")

        total_samples = int(round(time_points[-1] * sampling_frequency))
        voltage_waveform = np.ones(len(current), dtype=np.float32)
        initial_voltage = float(root.find(".//inital_UI_voltage").get("volt"))
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
        Find peaks in the current every time the voltage changes.
        The search for the peaks happens in the window of the timestamp 0.02 seconds.

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
        Parses the XML file and extracts metadata, handling missing elements gracefully.
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
        Extracts sampling frequency, total samples, and total time from the XML.
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
        """
        start_time = root.find(".//timestamp")
        if start_time is not None and "wall_clock" in start_time.attrib:
            return {"Acquisition start time": start_time.attrib["wall_clock"]}
        return {}

    def _extract_file_info(self):
        """
        Get filename metadata.
        """
        return {
            "DataFiles": [os.path.basename(self.xml_filename)],
            "StorageFormat": os.path.splitext(self.xml_filename)[-1]}

    def _calculate_bandwidth(self, metadata):
        """
        Final bandwidth based on sampling frequency.
        """
        sampling_frequency = metadata["Sampling frequency (SR)"]
        return {"Final Bandwidth": sampling_frequency / 2 if sampling_frequency < 200000 else 100000}

    def _load_opt_data(self):
        """
        Reads the current data from the .opt file.
        """
        try:
            dtype = np.dtype(">d")
            current = np.fromfile(self.opt_filename, dtype)
            return current
        except Exception as e:
            raise IOError(f"Error reading OPT file {self.opt_filename}: {e}")

    def _align_voltage(self, metadata, current_full):
        """
        Aligns the voltage to the current signal using XML metadata, starting
        from the first detected peak in the current data.
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
        Retrieves the starting sample index based on timestamp information.
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
        Processes time alignment marks to get the voltage waveform.
        The voltage alignment starts at current_index[first_peak_index - zero_voltage_samples].
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
        Processes the cap step waveform to add triangle wave segments.
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
        Apply "find_peaks" on a segment of the current data and return
        the indices of the found peak
        """
        # slice original data
        segment = current_data[start_index:end_index]

        peaks, properties = find_peaks(segment, height=1e-9)

        return peaks, properties


    

if __name__ == "__main__":
    # print(EDHReader.ext)
    #e = EDHReader()
    # meta, current, voltage = e.read("../../tests/data/8e7_80n01M1_5pctSorbitol_IV/"
    #                                 "8e7_80n01M1_5pctSorbitol_IV.edh", voltage_compress=True)

    # import matplotlib.pyplot as plt
    # plt.plot(current[::100])
    # plt.waitforbuttonpress()
    # e.read("C:/Users/alito/EDR/Q402m1_SBead/Q402m1_SBead.edh")


    opt_file_1 = "/Users/dinaraboyko/grad_school/cloned_repo/data/TOKW/B090624SR_100kHz__000.opt"

    opt_file_2 = "/Users/dinaraboyko/grad_school/cloned_repo/data/xialin/file 1/B110724SR_250kHz__006.opt"
    opt_file_3 = "/Users/dinaraboyko/grad_school/cloned_repo/data/011225/B011225_000--214219.opt"

    file = "/Users/dinaraboyko/grad_school/cloned_repo/data/openflowcel_dphpcPBD_PEO_dec_pretreatAR20_2MGdm_1MKCl_10_CH001/openflowcel_dphpcPBD_PEO_dec_pretreatAR20_2MGdm_1MKCl.edh"

    #metadata, current, voltage = EDHReader(file, voltage_compress=True, downsample=10)
    #print(metadata)

    metadata, current, voltage = OPTReader(opt_file_1, voltage_compress=True, downsample=1)
    print(metadata)

    # metadata, current, voltage = reader
    # print("Metadata:", metadata)
    # print("Curren:", len(current))
    # print("Voltage:", voltage)






