from datetime import datetime

import pytest

from pipeline.sync_shopify import (
    order_row,
    orders_query_filter,
    parse_timestamp,
    variant_rows,
)


def _variant(id_, title="Default Title", tracked=True, stock=5, sku=""):
    return {
        "id": id_,
        "sku": sku,
        "title": title,
        "inventoryQuantity": stock,
        "inventoryItem": {"tracked": tracked},
    }


def _product(title, variants, more=False):
    return {
        "title": title,
        "variants": {"pageInfo": {"hasNextPage": more}, "nodes": variants},
    }


def test_variant_rows_name_variants_and_skip_untracked_stock():
    rows = variant_rows(
        [
            _product("Board", [_variant("v1")]),
            _product("Wax", [_variant("v2", title="Blue", sku="W-B")]),
            _product("Untracked", [_variant("v3", tracked=False)]),
        ]
    )
    assert [r["description"] for r in rows] == ["Board", "Wax - Blue", "Untracked"]
    assert rows[0]["sku"] is None
    assert rows[1]["sku"] == "W-B"
    assert rows[2]["stock"] is None


def test_variant_rows_fail_loudly_on_truncated_variants():
    with pytest.raises(RuntimeError):
        variant_rows([_product("Big", [_variant("v1")], more=True)])


def _order(cancelled_at=None, variant=True):
    return {
        "id": "gid://shopify/Order/1",
        "processedAt": "2026-10-27T20:54:40Z",
        "updatedAt": "2026-11-17T10:00:00Z",
        "cancelledAt": cancelled_at,
        "lineItems": {
            "pageInfo": {"hasNextPage": False},
            "nodes": [
                {
                    "quantity": 2,
                    "variant": {"id": "v1"} if variant else None,
                    "originalUnitPriceSet": {"shopMoney": {"amount": "24.95"}},
                }
            ],
        },
    }


def test_order_row_parses_lines_and_dates():
    row = order_row(_order())
    assert row["order_date"] == datetime(2026, 10, 27, 20, 54, 40)
    assert row["is_cancelled"] is False
    assert row["lines"] == [{"variant_id": "v1", "quantity": 2, "unit_price": 24.95}]


def test_order_row_marks_cancelled_and_drops_lines_without_variant():
    row = order_row(_order(cancelled_at="2026-11-01T00:00:00Z", variant=False))
    assert row["is_cancelled"] is True
    assert row["lines"] == []


def test_parse_timestamp_converts_offsets_to_utc():
    assert parse_timestamp("2026-10-27T15:00:00-05:00") == datetime(2026, 10, 27, 20, 0)


def test_orders_query_filter():
    assert orders_query_filter(None) is None
    assert (
        orders_query_filter(datetime(2026, 11, 17, 10, 0))
        == "updated_at:>='2026-11-17T10:00:00Z'"
    )
