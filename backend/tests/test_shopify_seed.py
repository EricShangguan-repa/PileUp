import random
from datetime import UTC, datetime

from pipeline.seed_shopify import build_orders, seedable_variant_ids
from pipeline.shopify_client import throttle_wait_seconds


def _product(title, tracked=True, stock=10):
    return {
        "title": title,
        "variants": {
            "nodes": [
                {
                    "id": f"gid://{title}",
                    "inventoryQuantity": stock,
                    "inventoryItem": {"tracked": tracked},
                }
            ]
        },
    }


def test_seedable_variants_skip_special_untracked_and_out_of_stock():
    products = [
        _product("The Minimal Snowboard"),
        _product("Gift Card"),
        _product("The 3p Fulfilled Snowboard"),
        _product("Untracked", tracked=False),
        _product("Out of stock", stock=0),
    ]
    assert seedable_variant_ids(products) == ["gid://The Minimal Snowboard"]


def test_build_orders_are_tagged_test_orders_in_the_past():
    now = datetime(2026, 11, 17, tzinfo=UTC)
    orders = build_orders(["a", "b", "c"], 10, now, random.Random(0))
    assert len(orders) == 10
    for order in orders:
        assert order["test"] is True
        assert order["tags"] == ["pileup-seed"]
        assert datetime.fromisoformat(order["processedAt"]) < now
        assert 1 <= len(order["lineItems"]) <= 3


def test_throttle_wait():
    def cost(requested, available):
        return {
            "requestedQueryCost": requested,
            "throttleStatus": {"currentlyAvailable": available, "restoreRate": 100.0},
        }

    assert throttle_wait_seconds(None) == 0.0
    assert throttle_wait_seconds(cost(50, 1000)) == 0.0
    assert throttle_wait_seconds(cost(300, 100)) == 2.0
