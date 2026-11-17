import numpy as np

from pipeline.simulate_inventory import simulate_stock


def test_stock_is_within_days_of_cover_range():
    demand = np.array([10.0, 2.0, 0.0])
    stock = simulate_stock(demand, np.random.default_rng(0))
    assert 30 <= stock[0] <= 450
    assert 6 <= stock[1] <= 90
    assert stock[2] == 0


def test_same_seed_gives_same_stock():
    demand = np.array([5.0, 8.0])
    a = simulate_stock(demand, np.random.default_rng(42))
    b = simulate_stock(demand, np.random.default_rng(42))
    assert list(a) == list(b)
