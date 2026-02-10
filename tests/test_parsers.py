"""
Test module for parsers.py
"""

import pyximport
import numpy as np
import pytest
from ionique.parsers import SpikeParser
pyximport.install(setup_args={'include_dirs': np.get_include()})

# Simple data for test cases
current = np.array([0.1, 0.2, 0.3, 0.1, 0.2, 1.0, 1.5, 0.2, 0.3])
sampling_freq = 1000
mean = np.mean(current)
std = np.std(current)
start = 0


@pytest.fixture
def spike_parser():
	return SpikeParser(height=0.2, threshold=0.1)


# Test SpikeParser
def test_spike_parser_init(spike_parser):
	"""Test SpikeParser initialization"""

	assert spike_parser._height == 0.2
	assert spike_parser._threshold == 0.1
	assert spike_parser._distance is None
	assert spike_parser._prominence is None


# Test SpikeParser parser
def test_spike_parser_parse(spike_parser):
	"""Test SpikeParser parsing"""
	events = list(spike_parser.parse(current=current, sampling_freq=sampling_freq, mean=mean, std=std, start=start))
	assert len(events) > 0
	for event_start, event_end, unique_features in events:
		assert event_start < event_end
		assert 'idx_rel' in unique_features
		assert 'dwell' in unique_features
		assert 'dt' in unique_features




