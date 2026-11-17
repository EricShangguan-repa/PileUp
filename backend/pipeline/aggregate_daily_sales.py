import time

import pandas as pd
from sqlalchemy import text

from app.db import engine

SOURCE = "online_retail"


def compute_daily_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate order lines into daily sales per product.

    Zero-fills between each product's first and last sale date in the data
    (its active window), so a day with no sales is an explicit 0, not a
    missing row. Days outside that window are left out: the product wasn't
    yet introduced or was already discontinued, which isn't the same as a
    zero-demand day.

    df columns: product_id, order_date (datetime-like), quantity, unit_price
    returns columns: product_id, sale_date (date), quantity_sold, revenue
    """
    df = df.copy()
    df["sale_date"] = pd.to_datetime(df["order_date"]).dt.date
    df["line_revenue"] = df["quantity"] * df["unit_price"]

    daily = (
        df.groupby(["product_id", "sale_date"])
        .agg(quantity_sold=("quantity", "sum"), revenue=("line_revenue", "sum"))
        .reset_index()
    )

    filled = []
    for product_id, g in daily.groupby("product_id"):
        full_range = pd.date_range(
            g["sale_date"].min(), g["sale_date"].max(), freq="D"
        ).date
        g = g.set_index("sale_date").reindex(full_range, fill_value=0)
        g.index.name = "sale_date"
        g["product_id"] = product_id
        filled.append(g.reset_index())

    return pd.concat(filled, ignore_index=True)[
        ["product_id", "sale_date", "quantity_sold", "revenue"]
    ]


def main() -> None:
    t0 = time.time()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT ol.product_id, o.order_date, ol.quantity, ol.unit_price "
                "FROM order_lines ol JOIN orders o ON ol.order_id = o.id "
                "WHERE ol.source = :source"
            ),
            {"source": SOURCE},
        ).all()
    df = pd.DataFrame(
        rows, columns=["product_id", "order_date", "quantity", "unit_price"]
    )
    print(f"loaded {len(df):,} order lines in {time.time() - t0:.1f}s")

    daily = compute_daily_sales(df)
    print(
        f"computed {len(daily):,} daily sales rows for {daily['product_id'].nunique():,} products"
    )

    records = [
        {
            "product_id": int(r.product_id),
            "source": SOURCE,
            "sale_date": r.sale_date,
            "quantity_sold": int(r.quantity_sold),
            "revenue": float(r.revenue),
        }
        for r in daily.itertuples(index=False)
    ]
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM daily_sales WHERE source = :source"), {"source": SOURCE}
        )
        conn.execute(
            text(
                "INSERT INTO daily_sales (product_id, source, sale_date, quantity_sold, revenue) "
                "VALUES (:product_id, :source, :sale_date, :quantity_sold, :revenue)"
            ),
            records,
        )
    print(
        f"inserted {len(records):,} daily sales rows in {time.time() - t0:.1f}s total"
    )


if __name__ == "__main__":
    main()
