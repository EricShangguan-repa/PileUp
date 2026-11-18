from datetime import date, datetime

import numpy as np

from pipeline.seed_shopify_demand import (
    demand_variant_ids,
    pack_lines,
    plan_orders,
    scale_series,
    target_averages,
)


def test_scale_series_preserves_total_and_shape():
    series = np.array([10.0, 0.0, 30.0, 0.0, 60.0, 0.0, 0.0])
    scaled = scale_series(series, avg_per_day=1.0)
    assert scaled.sum() == 7
    assert (scaled >= 0).all()
    assert scaled[1] == 0 and scaled[3] == 0
    assert scaled[4] == scaled.max()


def test_target_averages_range():
    targets = target_averages(15)
    assert targets[0] == 2.0 and targets[-1] == 0.5
    assert list(targets) == sorted(targets, reverse=True)


def test_pack_lines_cycles_order_sizes():
    chunks = pack_lines(list(range(7)), (1, 2))
    assert [len(c) for c in chunks] == [1, 2, 1, 2, 1]
    assert [x for chunk in chunks for x in chunk] == list(range(7))


def test_plan_orders_skips_zero_days_and_dates_orders():
    units = {"a": np.array([1, 0, 2]), "b": np.array([3, 0, 0])}
    orders = plan_orders(units, date(2026, 9, 21), sizes=(1,))
    assert len(orders) == 3  # day 0: a and b; day 1: none; day 2: a
    days = [datetime.fromisoformat(o["processedAt"]).date() for o in orders]
    assert days == [date(2026, 9, 21), date(2026, 9, 21), date(2026, 9, 23)]
    assert sum(line["quantity"] for o in orders for line in o["lineItems"]) == 6
    assert all(o["test"] and o["tags"] == ["pileup-demand-seed"] for o in orders)


def test_demand_variants_ignore_stock_but_skip_special_products():
    def product(title, stock):
        return {
            "title": title,
            "variants": {
                "nodes": [
                    {
                        "id": title,
                        "inventoryQuantity": stock,
                        "inventoryItem": {"tracked": True},
                    }
                ]
            },
        }

    products = [
        product("Board", 0),
        product("The Out of Stock Snowboard", 0),
        product("Gift Card", 5),
    ]
    assert demand_variant_ids(products) == ["Board"]
