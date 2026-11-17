import pandas as pd

from pipeline.aggregate_daily_sales import compute_daily_sales


def test_sums_quantity_and_revenue_per_day():
    df = pd.DataFrame(
        [
            {
                "product_id": 1,
                "order_date": "2024-01-01",
                "quantity": 2,
                "unit_price": 5.0,
            },
            {
                "product_id": 1,
                "order_date": "2024-01-01",
                "quantity": 3,
                "unit_price": 5.0,
            },
        ]
    )
    daily = compute_daily_sales(df)
    assert len(daily) == 1
    row = daily.iloc[0]
    assert row["quantity_sold"] == 5
    assert row["revenue"] == 25.0


def test_zero_fills_gaps_within_active_window():
    df = pd.DataFrame(
        [
            {
                "product_id": 1,
                "order_date": "2024-01-01",
                "quantity": 2,
                "unit_price": 5.0,
            },
            {
                "product_id": 1,
                "order_date": "2024-01-03",
                "quantity": 1,
                "unit_price": 5.0,
            },
        ]
    )
    daily = compute_daily_sales(df).sort_values("sale_date").reset_index(drop=True)
    assert len(daily) == 3
    assert daily.iloc[1]["quantity_sold"] == 0
    assert daily.iloc[1]["revenue"] == 0


def test_does_not_fill_outside_product_active_window():
    df = pd.DataFrame(
        [
            {
                "product_id": 1,
                "order_date": "2024-01-05",
                "quantity": 1,
                "unit_price": 5.0,
            },
            {
                "product_id": 2,
                "order_date": "2024-01-01",
                "quantity": 1,
                "unit_price": 5.0,
            },
            {
                "product_id": 2,
                "order_date": "2024-01-10",
                "quantity": 1,
                "unit_price": 5.0,
            },
        ]
    )
    daily = compute_daily_sales(df)
    product_1_dates = set(daily[daily["product_id"] == 1]["sale_date"])
    assert product_1_dates == {pd.Timestamp("2024-01-05").date()}


def test_keeps_products_independent():
    df = pd.DataFrame(
        [
            {
                "product_id": 1,
                "order_date": "2024-01-01",
                "quantity": 1,
                "unit_price": 5.0,
            },
            {
                "product_id": 2,
                "order_date": "2024-01-01",
                "quantity": 1,
                "unit_price": 5.0,
            },
        ]
    )
    daily = compute_daily_sales(df)
    assert set(daily["product_id"]) == {1, 2}
