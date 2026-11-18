"""One-time seeding of the Shopify dev store with a small set of TEST orders.

Reuses the store's sample products. Orders are backdated over the last few weeks,
marked test=true, tagged pileup-seed, and reduce real stock. Dev stores allow about
5 new orders per minute, so this deliberately runs slowly (~7 minutes).
"""

import random
import time
from datetime import UTC, datetime, timedelta

from pipeline.shopify_client import ShopifyClient

SEED_TAG = "pileup-seed"
N_ORDERS = 30
DAYS_BACK = 42
SECONDS_BETWEEN_ORDERS = 13
SEED = 7
EXCLUDED_TITLE_WORDS = ("Gift Card", "Multi-location", "Multi-managed", "3p Fulfilled")

VARIANTS_QUERY = """
query($after: String) {
  products(first: 50, after: $after, query: "status:active") {
    pageInfo { hasNextPage endCursor }
    nodes {
      title
      variants(first: 10) {
        nodes { id inventoryQuantity inventoryItem { tracked } }
      }
    }
  }
}
"""

ORDER_CREATE = """
mutation($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
  orderCreate(order: $order, options: $options) {
    order { id name }
    userErrors { field message }
  }
}
"""


def seedable_variant_ids(products: list[dict]) -> list[str]:
    """Stock-tracked, in-stock variants of products without special fulfillment setups."""
    ids = []
    for product in products:
        if any(word in product["title"] for word in EXCLUDED_TITLE_WORDS):
            continue
        for variant in product["variants"]["nodes"]:
            if variant["inventoryItem"]["tracked"] and variant["inventoryQuantity"] > 0:
                ids.append(variant["id"])
    return ids


def build_orders(
    variant_ids: list[str], n_orders: int, now: datetime, rng: random.Random
) -> list[dict]:
    orders = []
    for _ in range(n_orders):
        processed_at = now - timedelta(
            days=rng.randint(1, DAYS_BACK), hours=rng.randint(0, 23)
        )
        picks = rng.sample(variant_ids, k=rng.randint(1, 3))
        orders.append(
            {
                "lineItems": [
                    {"variantId": v, "quantity": rng.randint(1, 2)} for v in picks
                ],
                "processedAt": processed_at.isoformat(),
                "financialStatus": "PAID",
                "test": True,
                "tags": [SEED_TAG],
            }
        )
    return orders


def fetch_products(client: ShopifyClient) -> list[dict]:
    products, after = [], None
    while True:
        page = client.graphql(VARIANTS_QUERY, {"after": after})["products"]
        products += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return products
        after = page["pageInfo"]["endCursor"]


def main() -> None:
    client = ShopifyClient()
    existing = client.graphql(
        "query($q: String) { ordersCount(query: $q) { count } }",
        {"q": f"tag:{SEED_TAG}"},
    )["ordersCount"]["count"]
    if existing >= N_ORDERS:
        print(f"store already has {existing} {SEED_TAG} orders; nothing to do")
        return

    variant_ids = seedable_variant_ids(fetch_products(client))
    orders = build_orders(variant_ids, N_ORDERS, datetime.now(UTC), random.Random(SEED))
    print(
        f"{existing} already seeded; creating {N_ORDERS - existing} more "
        f"across {len(variant_ids)} variants"
    )
    for i, order in enumerate(orders[existing:], start=existing + 1):
        result = client.graphql(
            ORDER_CREATE,
            {
                "order": order,
                "options": {
                    "inventoryBehaviour": "DECREMENT_IGNORING_POLICY",
                    "sendReceipt": False,
                    "sendFulfillmentReceipt": False,
                },
            },
        )["orderCreate"]
        if result["userErrors"]:
            raise SystemExit(f"order {i} failed: {result['userErrors']}")
        print(f"{i}/{N_ORDERS} created {result['order']['name']}")
        if i < N_ORDERS:
            time.sleep(SECONDS_BETWEEN_ORDERS)


if __name__ == "__main__":
    main()
