import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.db import engine
from pipeline.transform import clean_online_retail

SOURCE = "online_retail"
XLSX_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "raw" / "online_retail_II.xlsx"
)
SHEETS = ["Year 2009-2010", "Year 2010-2011"]


def load_raw() -> pd.DataFrame:
    if not XLSX_PATH.exists():
        print(f"Missing dataset at {XLSX_PATH}. Download it first.", file=sys.stderr)
        sys.exit(1)
    frames = [pd.read_excel(XLSX_PATH, sheet_name=sheet) for sheet in SHEETS]
    return pd.concat(frames, ignore_index=True)


def upsert_products(conn, df: pd.DataFrame) -> dict[str, int]:
    products = df[["StockCode", "Description"]].drop_duplicates("StockCode")
    rows = [
        {
            "source": SOURCE,
            "source_product_id": row.StockCode,
            "sku": row.StockCode,
            "description": None
            if pd.isna(row.Description)
            else str(row.Description)[:255],
        }
        for row in products.itertuples(index=False)
    ]
    conn.execute(
        text(
            "INSERT INTO products (source, source_product_id, sku, description) "
            "VALUES (:source, :source_product_id, :sku, :description) "
            "ON DUPLICATE KEY UPDATE description = VALUES(description)"
        ),
        rows,
    )
    ids = conn.execute(
        text("SELECT source_product_id, id FROM products WHERE source = :source"),
        {"source": SOURCE},
    )
    return {sp_id: pid for sp_id, pid in ids}


def upsert_orders(conn, df: pd.DataFrame) -> dict[str, int]:
    orders = df[["Invoice", "InvoiceDate", "Customer ID", "Country"]].drop_duplicates(
        "Invoice"
    )
    orders = orders.rename(columns={"Customer ID": "CustomerId"})
    for row in orders.itertuples(index=False):
        customer_id = None if pd.isna(row.CustomerId) else str(int(row.CustomerId))
        conn.execute(
            text(
                "INSERT INTO orders (source, source_order_id, order_date, customer_id, country, is_cancelled) "
                "VALUES (:source, :source_order_id, :order_date, :customer_id, :country, FALSE) "
                "ON DUPLICATE KEY UPDATE order_date = VALUES(order_date)"
            ),
            {
                "source": SOURCE,
                "source_order_id": row.Invoice,
                "order_date": row.InvoiceDate.to_pydatetime(),
                "customer_id": customer_id,
                "country": row.Country,
            },
        )
    ids = conn.execute(
        text("SELECT source_order_id, id FROM orders WHERE source = :source"),
        {"source": SOURCE},
    )
    return {sp_id: pid for sp_id, pid in ids}


def insert_order_lines(
    conn, df: pd.DataFrame, product_map: dict[str, int], order_map: dict[str, int]
) -> int:
    conn.execute(
        text(
            "DELETE ol FROM order_lines ol JOIN orders o ON ol.order_id = o.id WHERE o.source = :source"
        ),
        {"source": SOURCE},
    )
    rows = [
        {
            "order_id": order_map[row.Invoice],
            "product_id": product_map[row.StockCode],
            "source": SOURCE,
            "quantity": int(row.Quantity),
            "unit_price": float(row.Price),
        }
        for row in df.itertuples(index=False)
    ]
    if rows:
        conn.execute(
            text(
                "INSERT INTO order_lines (order_id, product_id, source, quantity, unit_price) "
                "VALUES (:order_id, :product_id, :source, :quantity, :unit_price)"
            ),
            rows,
        )
    return len(rows)


def main() -> None:
    t0 = time.time()
    raw = load_raw()
    print(f"loaded {len(raw):,} raw rows in {time.time() - t0:.1f}s")

    cleaned = clean_online_retail(raw)
    dropped = len(raw) - len(cleaned)
    print(f"kept {len(cleaned):,} rows after cleaning, dropped {dropped:,}")

    with engine.begin() as conn:
        product_map = upsert_products(conn, cleaned)
        print(f"upserted {len(product_map):,} products")
        order_map = upsert_orders(conn, cleaned)
        print(f"upserted {len(order_map):,} orders")
        n_lines = insert_order_lines(conn, cleaned, product_map, order_map)
        print(f"inserted {n_lines:,} order lines")

    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
