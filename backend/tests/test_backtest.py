from datetime import date, timedelta

import pandas as pd

from forecast.backtest import backtest_series, full_series, make_cutoffs


def test_make_cutoffs_leaves_room_for_full_horizon():
    cutoffs = make_cutoffs(date(2024, 1, 1), date(2024, 1, 31), horizon=10, step=7)
    assert cutoffs == [date(2024, 1, 1), date(2024, 1, 8), date(2024, 1, 15)]


def test_backtest_never_trains_on_future_days():
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(20)]
    # sales jump to 100 after the cutoff; the naive model must not see that
    values = [1.0] * 10 + [100.0] * 10
    series = pd.Series(values, index=days)
    results = backtest_series(series, [date(2024, 1, 10)], horizon=5)
    naive = results[results["model"] == "naive"]
    assert len(naive) == 5
    assert (naive["predicted"] == 1.0).all()
    assert (naive["actual"] == 100.0).all()
    assert naive["horizon_date"].min() == date(2024, 1, 11)


def test_full_series_zero_fills_after_last_sale():
    sales = pd.DataFrame(
        {"sale_date": [date(2024, 1, 1), date(2024, 1, 2)], "quantity_sold": [3, 4]}
    )
    series = full_series(sales, date(2024, 1, 4))
    assert list(series) == [3.0, 4.0, 0.0, 0.0]
