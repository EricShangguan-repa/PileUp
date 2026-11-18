"""Sync products, stock levels and orders from the Shopify dev store into MySQL.

Products and stock are re-read in full each run (the store is small). Orders are
incremental: only orders updated since the last sync are fetched.
"""

from datetime import UTC, datetime

from sqlalchemy import bindparam, text

from app.db import engine
from pipeline.shopify_client import ShopifyClient

SOURCE = "shopify"

PRODUCTS_QUERY = """
query($after: String) {
  products(first: 20, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      title
      variants(first: 25) {
        pageInfo { hasNextPage }
        nodes { id sku title inventoryQuantity inventoryItem { tracked } }
      }
    }
  }
}
"""

ORDERS_QUERY = """
query($after: String, $q: String) {
  orders(first: 25, after: $after, query: $q, sortKey: UPDATED_AT) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      processedAt
      updatedAt
      cancelledAt
      lineItems(first: 20) {
        pageInfo { hasNextPage }
        nodes {
          quantity
          variant { id }
          originalUnitPriceSet { shopMoney { amount } }
        }
      }
    }
  }
}
"""


def parse_timestamp(value: str) -> datetime:
    """Shopify ISO timestamp -> naive UTC datetime, the format stored in MySQL."""
    return datetime.fromisoformat(value).astimezone(UTC).replace(tzinfo=None)


def variant_rows(products: list[dict]) -> list[dict]:
    """One PileUp product per Shopify variant (the unit Shopify sells and stocks)."""
    rows = []
    for product in products:
        variants = product["variants"]
        if variants["pageInfo"]["hasNextPage"]:
            raise RuntimeError(f"{product['title']} has more variants than one page")
        for variant in variants["nodes"]:
            name = product["title"]
            if variant["title"] != "Default Title":
                name = f"{name} - {variant['title']}"
            rows.append(
                {
                    "source_product_id": variant["id"],
                    "sku": variant["sku"] or None,
                    "description": name[:255],
                    "stock": variant["inventoryQuantity"]
                    if variant["inventoryItem"]["tracked"]
                    else None,
                }
            )
    return rows


def order_row(order: dict) -> dict:
    """Order fields plus its line items; lines with no variant (deleted products,
    custom items) can't be linked to a product, so they're dropped."""
    line_items = order["lineItems"]
    if line_items["pageInfo"]["hasNextPage"]:
        raise RuntimeError(f"order {order['id']} has more line items than one page")
    return {
        "source_order_id": order["id"],
        "order_date": parse_timestamp(order["processedAt"]),
        "is_cancelled": order["cancelledAt"] is not None,
        "lines": [
            {
                "variant_id": line["variant"]["id"],
                "quantity": line["quantity"],
                "unit_price": float(
                    line["originalUnitPriceSet"]["shopMoney"]["amount"]
                ),
            }
            for line in line_items["nodes"]
            if line["variant"] is not None
        ],
    }


def orders_query_filter(last_synced_at: datetime | None) -> str | None:
    """Shopify search filter for incremental sync. Uses >= so an order updated in
    the same second as the last sync isn't missed; re-upserting it is harmless."""
    if last_synced_at is None:
        return None
    return f"updated_at:>='{last_synced_at.isoformat()}Z'"


def fetch_all(
    client: ShopifyClient, query: str, key: str, variables: dict
) -> list[dict]:
    nodes, after = [], None
    while True:
        page = client.graphql(query, {**variables, "after": after})[key]
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        after = page["pageInfo"]["endCursor"]


def save_products(conn, rows: list[dict]) -> dict[str, int]:
    conn.execute(
        text(
            "INSERT INTO products (source, source_product_id, sku, description) "
            "VALUES (:source, :source_product_id, :sku, :description) "
            "ON DUPLICATE KEY UPDATE sku = VALUES(sku), description = VALUES(description)"
        ),
        [{**r, "source": SOURCE} for r in rows],
    )
    ids = conn.execute(
        text("SELECT source_product_id, id FROM products WHERE source = :source"),
        {"source": SOURCE},
    )
    return {sp_id: pid for sp_id, pid in ids}


def save_stock(conn, rows: list[dict], product_map: dict[str, int]) -> int:
    today = datetime.now(UTC).date()
    stock_rows = [
        {
            "product_id": product_map[r["source_product_id"]],
            "source": SOURCE,
            "snapshot_date": today,
            "stock_quantity": r["stock"],
        }
        for r in rows
        if r["stock"] is not None
    ]
    conn.execute(
        text(
            "INSERT INTO inventory_snapshots "
            "(product_id, source, snapshot_date, stock_quantity, is_simulated) "
            "VALUES (:product_id, :source, :snapshot_date, :stock_quantity, FALSE) "
            "ON DUPLICATE KEY UPDATE stock_quantity = VALUES(stock_quantity)"
        ),
        stock_rows,
    )
    return len(stock_rows)


def save_orders(conn, orders: list[dict], product_map: dict[str, int]) -> int:
    conn.execute(
        text(
            "INSERT INTO orders (source, source_order_id, order_date, is_cancelled) "
            "VALUES (:source, :source_order_id, :order_date, :is_cancelled) "
            "ON DUPLICATE KEY UPDATE order_date = VALUES(order_date), "
            "is_cancelled = VALUES(is_cancelled)"
        ),
        [
            {
                "source": SOURCE,
                "source_order_id": o["source_order_id"],
                "order_date": o["order_date"],
                "is_cancelled": o["is_cancelled"],
            }
            for o in orders
        ],
    )
    order_ids = dict(
        conn.execute(
            text("SELECT source_order_id, id FROM orders WHERE source = :source"),
            {"source": SOURCE},
        ).all()
    )
    synced_ids = [order_ids[o["source_order_id"]] for o in orders]
    conn.execute(
        text("DELETE FROM order_lines WHERE order_id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"ids": synced_ids},
    )
    lines = [
        {
            "order_id": order_ids[o["source_order_id"]],
            "product_id": product_map[line["variant_id"]],
            "source": SOURCE,
            "quantity": line["quantity"],
            "unit_price": line["unit_price"],
        }
        for o in orders
        for line in o["lines"]
        if line["variant_id"] in product_map
    ]
    if lines:
        conn.execute(
            text(
                "INSERT INTO order_lines (order_id, product_id, source, quantity, unit_price) "
                "VALUES (:order_id, :product_id, :source, :quantity, :unit_price)"
            ),
            lines,
        )
    return len(lines)


def main() -> None:
    client = ShopifyClient()
    with engine.begin() as conn:
        last_synced_at = conn.execute(
            text("SELECT last_synced_at FROM sync_state WHERE source = :source"),
            {"source": SOURCE},
        ).scalar_one_or_none()

    products = variant_rows(fetch_all(client, PRODUCTS_QUERY, "products", {}))
    raw_orders = fetch_all(
        client, ORDERS_QUERY, "orders", {"q": orders_query_filter(last_synced_at)}
    )
    orders = [order_row(o) for o in raw_orders]
    print(
        f"fetched {len(products)} variants and {len(orders)} orders "
        f"({'since ' + str(last_synced_at) if last_synced_at else 'full sync'})"
    )

    with engine.begin() as conn:
        product_map = save_products(conn, products)
        n_stock = save_stock(conn, products, product_map)
        n_lines = save_orders(conn, orders, product_map) if orders else 0
        if raw_orders:
            newest = max(parse_timestamp(o["updatedAt"]) for o in raw_orders)
            conn.execute(
                text(
                    "INSERT INTO sync_state (source, last_synced_at) VALUES (:source, :ts) "
                    "ON DUPLICATE KEY UPDATE last_synced_at = VALUES(last_synced_at)"
                ),
                {"source": SOURCE, "ts": newest},
            )
    print(
        f"saved {len(product_map)} products, {n_stock} stock levels, {n_lines} order lines"
    )


if __name__ == "__main__":
    main()
