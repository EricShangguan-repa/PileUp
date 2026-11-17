import numpy as np


def naive(history: np.ndarray, horizon: int) -> np.ndarray:
    return np.full(horizon, float(history[-1]))


def seasonal_naive(history: np.ndarray, horizon: int, season: int = 7) -> np.ndarray:
    last_season = history[-season:].astype(float)
    return np.resize(last_season, horizon)


def moving_average(history: np.ndarray, horizon: int, window: int) -> np.ndarray:
    return np.full(horizon, float(history[-window:].mean()))


MODELS = {
    "naive": naive,
    "seasonal_naive": seasonal_naive,
    "moving_average_7": lambda h, n: moving_average(h, n, 7),
    "moving_average_28": lambda h, n: moving_average(h, n, 28),
}


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Sum of absolute errors over sum of actuals. Unlike MAPE, zero-sale days don't break it."""
    return float(np.sum(np.abs(actual - predicted)) / np.sum(actual))


def days_to_stockout(current_stock: float, daily_demand: float) -> float | None:
    """None means no forecast demand, so the product never runs out at this rate."""
    if daily_demand <= 0:
        return None
    return current_stock / daily_demand
