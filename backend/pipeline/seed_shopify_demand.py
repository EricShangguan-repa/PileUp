"""Seed the Shopify dev store with SYNTHETIC test orders shaped on real demand.

Each seedable store variant is paired with one of the top UK products (Online
Retail II). That product's daily demand over a 56-day window (2011-09-12 to
2011-11-06, Monday to Sunday) is scaled down to 0.5-2 units/day and replayed onto
the store's calendar 2026-09-21 to 2026-11-15 (also Monday to Sunday), so the
weekly pattern (almost no Saturday orders) and the spikes are kept.

Steps, each safe to rerun:
1. delete the earlier random `pileup-seed` orders
2. create the planned orders (resumes from the count already created)
3. set each variant's stock to a random 5-40 days of its average demand

These are test orders and script-set stock in a test store: never report Shopify
forecast accuracy from them as a real result.
"""

import json
import random
import time
import uuid
from datetime import date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path

import numpy as np
from sqlalchemy import text

from app.db import engine
from pipeline.seed_shopify import EXCLUDED_TITLE_WORDS, fetch_products
from pipeline.seed_shopify import SEED_TAG as RANDOM_SEED_TAG
from pipeline.shopify_client import ShopifyClient

TAG = "pileup-demand-seed"
UK_START = date(2011, 9, 12)
STORE_START = date(2026, 9, 21)
WINDOW_DAYS = 56
ORDER_SIZES = (1, 2)  # lines per order, cycled: ~300 orders for this plan
MIN_AVG_PER_DAY, MAX_AVG_PER_DAY = 0.5, 2.0
STOCK_DAYS_RANGE = (5, 40)
SEED = 11
SECONDS_BETWEEN_ORDERS = 13
RESULTS_PATH = Path(__file__).resolve().parents[2] / "docs" / "backtest_results.json"

ORDER_CREATE = """
mutation($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
  orderCreate(order: $order, options: $options) {
    order { id }
    userErrors { field message }
  }
}
"""

ORDER_DELETE = """
mutation($id: ID!) {
  orderDelete(orderId: $id) { deletedId userErrors { field message code } }
}
"""

TAGGED_ORDER_IDS = """
query($q: String, $after: String) {
  orders(first: 50, after: $after, query: $q) {
    pageInfo { hasNextPage endCursor }
    nodes { id }
  }
}
"""

INVENTORY_LEVELS = """
query($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on ProductVariant {
      id
      inventoryItem { id inventoryLevels(first: 1) { nodes { location { id } } } }
    }
  }
}
"""

INVENTORY_SET = """
mutation($input: InventorySetQuantitiesInput!, $idempotencyKey: String!) {
  inventorySetQuantities(input: $input) @idempotent(key: $idempotencyKey) {
    userErrors { code field message }
  }
}
"""


def demand_variant_ids(products: list[dict]) -> list[str]:
    """Like seed_shopify.seedable_variant_ids but independent of current stock, so the
    plan stays the same on reruns. The Out of Stock board is left alone on purpose."""
    return [
        variant["id"]
        for product in products
        if not any(
            w in product["title"] for w in (*EXCLUDED_TITLE_WORDS, "Out of Stock")
        )
        for variant in product["variants"]["nodes"]
        if variant["inventoryItem"]["tracked"]
    ]


def scale_series(series: np.ndarray, avg_per_day: float) -> np.ndarray:
    """Scale to the target average, rounding so the total is preserved exactly:
    each day gets round(cumulative) - round(previous cumulative)."""
    scaled = series * (avg_per_day * len(series) / series.sum())
    cumulative = np.round(np.cumsum(scaled))
    return np.diff(np.concatenate([[0], cumulative])).astype(int)


def target_averages(n: int) -> np.ndarray:
    """Higher-revenue UK products get busier store variants: 2.0 down to 0.5/day."""
    return np.linspace(MAX_AVG_PER_DAY, MIN_AVG_PER_DAY, n)


def pack_lines(lines: list, sizes: tuple[int, ...]) -> list[list]:
    """Split a day's lines into orders whose sizes cycle through `sizes`."""
    chunks, i, k = [], 0, 0
    while i < len(lines):
        size = sizes[k % len(sizes)]
        chunks.append(lines[i : i + size])
        i += size
        k += 1
    return chunks


def plan_orders(
    daily_units: dict[str, np.ndarray], store_start: date, sizes: tuple[int, ...]
) -> list[dict]:
    """Turn per-variant daily units into dated orders sized by `sizes`."""
    n_days = len(next(iter(daily_units.values())))
    orders = []
    for day in range(n_days):
        lines = [
            {"variantId": vid, "quantity": int(units[day])}
            for vid, units in daily_units.items()
            if units[day] > 0
        ]
        for slot, chunk in enumerate(pack_lines(lines, sizes)):
            processed_at = datetime.combine(
                store_start + timedelta(days=day), dtime(9 + (slot * 3) % 10, 0)
            )
            orders.append(
                {
                    "lineItems": chunk,
                    "processedAt": processed_at.isoformat() + "Z",
                    "financialStatus": "PAID",
                    "test": True,
                    "tags": [TAG],
                }
            )
    return orders


def load_uk_windows(product_ids: list[int]) -> list[np.ndarray]:
    end = UK_START + timedelta(days=WINDOW_DAYS - 1)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT product_id, sale_date, quantity_sold FROM daily_sales "
                "WHERE source = 'online_retail' AND sale_date BETWEEN :start AND :end"
            ),
            {"start": UK_START, "end": end},
        ).all()
    days = [UK_START + timedelta(days=i) for i in range(WINDOW_DAYS)]
    by_product: dict[int, dict[date, int]] = {}
    for pid, d, q in rows:
        by_product.setdefault(pid, {})[d] = q
    return [
        np.array([by_product.get(pid, {}).get(d, 0) for d in days], dtype=float)
        for pid in product_ids
    ]


def build_plan(variant_ids: list[str]) -> tuple[list[dict], dict[str, float]]:
    uk_ids = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))["product_ids"]
    windows = [w for w in load_uk_windows(uk_ids) if w.sum() > 0][: len(variant_ids)]
    targets = target_averages(len(variant_ids))
    daily_units = {
        vid: scale_series(w, t) for vid, w, t in zip(variant_ids, windows, targets)
    }
    avg_demand = {vid: units.mean() for vid, units in daily_units.items()}
    return plan_orders(daily_units, STORE_START, ORDER_SIZES), avg_demand


def tagged_order_ids(client: ShopifyClient, tag: str) -> list[str]:
    ids, after = [], None
    while True:
        page = client.graphql(TAGGED_ORDER_IDS, {"q": f"tag:{tag}", "after": after})[
            "orders"
        ]
        ids += [n["id"] for n in page["nodes"]]
        if not page["pageInfo"]["hasNextPage"]:
            return ids
        after = page["pageInfo"]["endCursor"]


def delete_random_seed_orders(client: ShopifyClient) -> None:
    ids = tagged_order_ids(client, RANDOM_SEED_TAG)
    for order_id in ids:
        result = client.graphql(ORDER_DELETE, {"id": order_id})["orderDelete"]
        if result["userErrors"]:
            raise SystemExit(f"deleting {order_id} failed: {result['userErrors']}")
    print(f"deleted {len(ids)} earlier random {RANDOM_SEED_TAG} orders")


def create_orders(client: ShopifyClient, orders: list[dict]) -> None:
    existing = client.graphql(
        "query($q: String) { ordersCount(query: $q) { count } }", {"q": f"tag:{TAG}"}
    )["ordersCount"]["count"]
    print(f"{existing}/{len(orders)} {TAG} orders already exist")
    for i, order in enumerate(orders[existing:], start=existing + 1):
        result = client.graphql(
            ORDER_CREATE,
            {
                "order": order,
                "options": {
                    "inventoryBehaviour": "BYPASS",
                    "sendReceipt": False,
                    "sendFulfillmentReceipt": False,
                },
            },
        )["orderCreate"]
        if result["userErrors"]:
            raise SystemExit(f"order {i} failed: {result['userErrors']}")
        if i % 25 == 0 or i == len(orders):
            print(f"{i}/{len(orders)} created", flush=True)
        if i < len(orders):
            time.sleep(SECONDS_BETWEEN_ORDERS)


def set_stock(client: ShopifyClient, avg_demand: dict[str, float]) -> None:
    rng = random.Random(SEED)
    targets = {
        vid: round(avg * rng.uniform(*STOCK_DAYS_RANGE))
        for vid, avg in avg_demand.items()
    }
    nodes = client.graphql(INVENTORY_LEVELS, {"ids": list(targets)})["nodes"]
    quantities = [
        {
            "inventoryItemId": n["inventoryItem"]["id"],
            "locationId": n["inventoryItem"]["inventoryLevels"]["nodes"][0]["location"][
                "id"
            ],
            "quantity": targets[n["id"]],
            "changeFromQuantity": None,
        }
        for n in nodes
    ]
    result = client.graphql(
        INVENTORY_SET,
        {
            "input": {
                "name": "available",
                "reason": "correction",
                "quantities": quantities,
            },
            "idempotencyKey": str(uuid.uuid4()),
        },
    )["inventorySetQuantities"]
    if result["userErrors"]:
        raise SystemExit(f"setting stock failed: {result['userErrors']}")
    print(f"set test-store stock for {len(quantities)} variants")


def main() -> None:
    client = ShopifyClient()
    variant_ids = demand_variant_ids(fetch_products(client))
    orders, avg_demand = build_plan(variant_ids)
    print(
        f"plan: {len(orders)} orders, "
        f"{sum(len(o['lineItems']) for o in orders)} lines, "
        f"{sum(line['quantity'] for o in orders for line in o['lineItems'])} units "
        f"across {len(variant_ids)} variants"
    )
    delete_random_seed_orders(client)
    create_orders(client, orders)
    set_stock(client, avg_demand)


if __name__ == "__main__":
    main()
