"""
Test module for io.py
"""
import xml.etree.ElementTree as ET
import pytest
import os
from ionique.io import EDHReader, OPTReader
import numpy as np

# Test EDH reader
@pytest.fixture
def path_to_file():
    return "data/8e7_80n01M1_5pctSorbitol_IV/8e7_80n01M1_5pctSorbitol_IV.edh"


def test_edh_reader(path_to_file):
    """Test EDH reader"""
    edh_reader = EDHReader()
    assert os.path.exists(path_to_file), f"EDH file not found at {path_to_file}"

    # Read the file
    metadata, current, voltage = edh_reader.read(path_to_file)
    # Check keys in metadata
    assert "EDH Version" in metadata
    # Check the current is read and it is not empty
    assert current is not None
    assert len(current) > 0
    # Check the voltage is read and it is not empty
    assert voltage is not None
    assert len(voltage) > 0


#########################################
# Test for OPTReader
#########################################

opt_file_voltage = "/Users/dinaraboyko/grad_school/cloned_repo/data/011225/B011225_000--214219.opt"
xml_file_triangle_wave = "/Users/dinaraboyko/grad_school/cloned_repo/data/TOKW/B090624SR_100kHz__000.xml"
xml_file_regular = "/Users/dinaraboyko/grad_school/cloned_repo/data/xialin/file 1/B110724SR_250kHz__006.opt"
#
#
# def test_init_with_opt_file(opt_file):
#
#     opt_reader = OPTReader(str(opt_file))
#
#     assert opt_reader.opt_filename == str(opt_file)
#     assert hasattr(opt_reader, "metadata")
#     assert hasattr(opt_reader, "current")
#     assert hasattr(opt_reader, "voltage")
#
#
# def test_init_with_volt_file(opt_volt_file):
#
#     opt_reader = OPTReader(str(opt_volt_file), voltage_compress=True)
#
#     assert opt_reader.opt_filename == str(opt_volt_file)
#     assert hasattr(opt_reader, "metadata")
#     assert hasattr(opt_reader, "current")
#     assert opt_reader.voltage is not None
#
#
# def test_init_with_xml_file(xml_file):
#     """
#     Test initializing the OPTReader with an XML file.
#     """
#     opt_reader = OPTReader(str(xml_file))
#
#     assert opt_reader.xml_filename == str(xml_file)
#     assert hasattr(opt_reader, "metadata")
#     assert hasattr(opt_reader, "current")
#     assert hasattr(opt_reader, "voltage")
#
#
# def test_downsampling(opt_file):
#
#     downsample_rate = 10
#     opt_reader = OPTReader(str(opt_file), downsample=downsample_rate)
#
#     assert len(opt_reader.current) > 0
#     if opt_reader.voltage is not None:
#         assert len(opt_reader.voltage) > 0
#
#
# def test_metadata_parsing(xml_file):
#
#     opt_reader = OPTReader(str(xml_file))
#
#     metadata = opt_reader.metadata
#     assert "HeaderFile" in metadata
#     assert "Sampling frequency (SR)" in metadata
#
#
# def test_voltage_compression(opt_volt_file):
#
#     opt_reader = OPTReader(str(opt_volt_file), voltage_compress=True)
#
#     voltage_points = opt_reader.voltage
#     assert isinstance(voltage_points, list)
#     for segment, voltage in voltage_points:
#         assert isinstance(segment, slice)
#         assert isinstance(voltage, float)
