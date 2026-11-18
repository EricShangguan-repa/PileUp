from datetime import date

import pandas as pd

from forecast.forecast_shopify import future_rows


def test_future_rows_forecast_each_product_after_last_day():
    sales = pd.DataFrame(
        {
            "product_id": [1, 1, 2],
            "sale_date": [date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 2)],
            "quantity_sold": [4, 2, 6],
        }
    )
    rows = future_rows(sales, date(2026, 11, 3), "moving_average_7", horizon=3)
    assert len(rows) == 6
    product_1 = [r for r in rows if r["product_id"] == 1]
    assert [r["horizon_date"] for r in product_1] == [
        date(2026, 11, 4),
        date(2026, 11, 5),
        date(2026, 11, 6),
    ]
    # 3-day history 4, 2, 0 (zero-filled to last_day); the 7-day mean uses what exists
    assert product_1[0]["predicted_quantity"] == 2.0
    assert all(r["source"] == "shopify" for r in rows)
