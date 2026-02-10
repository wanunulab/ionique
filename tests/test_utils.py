"""
Test module for utils.py
"""

from ionique.utils import *
import pytest
import numpy as np


class SingletonClass(metaclass=Singleton):
    """
    Check if Singleton class creates only one instance
    """
    def __init__(self, value):
        self.value = value


# Test instance of Singleton
def test_singleton():
    instance_1 = SingletonClass(10)
    assert instance_1.value == 10
    instance_2 = SingletonClass(20)
    # do both instances point to the same object?
    assert instance_1 is instance_2


# This decorator is to generate test cases for "split_voltage_steps"
@pytest.mark.parametrize(
    "voltage, n_remove, as_tuples, expected",
    [
        # first case: standard split
        (np.array([0, 0, 1, 1, 2, 2]), 0, False, (np.array([0, 2, 4]), np.array([2, 4, 6]))),
        # n_remove = 1
        (np.array([0, 0, 1, 1, 2, 2]), 1, False, (np.array([1, 3, 5]), np.array([2, 4, 6]))),
        # as_tuples=True
        (np.array([0, 0, 1, 1, 2, 2]), 0, True, [(0, 2), (2, 4), (4, 6)]),
        # case with empty array
        (np.array([]), 0, False, ([], []))
    ]
)
def test_split_voltage_steps(voltage, n_remove, as_tuples, expected):
    """
    Test for split_voltage_steps. It takes a decorator as arguments
    """
    result = split_voltage_steps(voltage, n_remove, as_tuples)
    assert np.allclose(result, expected, equal_nan=True)


def test_split_voltage_steps_errors():
    """
    Test error raising
    """
    # Test for ValueError if n_remove is negative
    voltage = np.array([0, 1, 2])
    with pytest.raises(ValueError, match="n_remove must be non-negative"):
        split_voltage_steps(voltage, n_remove=-1)

    # Test for ValueError if n_remove is too large
    voltage = np.array([0, 0, 1, 1, 2, 2])
    with pytest.raises(ValueError, match="n_remove is too large"):
        split_voltage_steps(voltage, n_remove=5)
