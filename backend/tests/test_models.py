import numpy as np
import pytest

from forecast.models import (
    days_to_stockout,
    mae,
    moving_average,
    naive,
    seasonal_naive,
    wape,
)


def test_naive_repeats_last_value():
    assert list(naive(np.array([1, 2, 5]), 3)) == [5, 5, 5]


def test_seasonal_naive_repeats_last_week():
    history = np.array([0, 0, 1, 2, 3, 4, 5, 6, 7])
    assert list(seasonal_naive(history, 9)) == [1, 2, 3, 4, 5, 6, 7, 1, 2]


def test_moving_average_uses_last_window():
    history = np.array([100, 1, 2, 3])
    assert list(moving_average(history, 2, window=3)) == [2.0, 2.0]


def test_mae_and_wape():
    actual = np.array([0, 10, 10])
    predicted = np.array([2, 8, 10])
    assert mae(actual, predicted) == pytest.approx(4 / 3)
    assert wape(actual, predicted) == pytest.approx(4 / 20)


def test_wape_handles_zero_actual_days():
    assert wape(np.array([0, 0, 4]), np.array([1, 0, 4])) == pytest.approx(0.25)


def test_days_to_stockout():
    assert days_to_stockout(100, 10) == 10
    assert days_to_stockout(100, 0) is None
