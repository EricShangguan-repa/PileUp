import numpy as np
from sqlalchemy import text

from app.db import engine

SOURCE = "online_retail"
SEED = 42
MIN_DAYS_OF_COVER = 3
MAX_DAYS_OF_COVER = 45


def simulate_stock(
    avg_daily_demand: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Online Retail II has no inventory data, so stock is SIMULATED: recent average
    demand times a random 3-45 days of cover. Never present this as real stock."""
    days_of_cover = rng.uniform(
        MIN_DAYS_OF_COVER, MAX_DAYS_OF_COVER, len(avg_daily_demand)
    )
    return np.round(avg_daily_demand * days_of_cover).astype(int)


def main() -> None:
    with engine.begin() as conn:
        snapshot_date = conn.execute(
            text(
                "SELECT MAX(forecast_made_date) FROM forecasts WHERE source = :source"
            ),
            {"source": SOURCE},
        ).scalar_one()
        rows = conn.execute(
            text(
                "SELECT ds.product_id, AVG(ds.quantity_sold) "
                "FROM daily_sales ds "
                "WHERE ds.source = :source "
                "AND ds.product_id IN (SELECT DISTINCT product_id FROM forecasts WHERE source = :source) "
                "AND ds.sale_date > DATE_SUB(:snapshot_date, INTERVAL 28 DAY) "
                "AND ds.sale_date <= :snapshot_date "
                "GROUP BY ds.product_id ORDER BY ds.product_id"
            ),
            {"source": SOURCE, "snapshot_date": snapshot_date},
        ).all()
        product_ids = [r[0] for r in rows]
        stock = simulate_stock(
            np.array([float(r[1]) for r in rows]), np.random.default_rng(SEED)
        )

        conn.execute(
            text("DELETE FROM inventory_snapshots WHERE source = :source"),
            {"source": SOURCE},
        )
        conn.execute(
            text(
                "INSERT INTO inventory_snapshots "
                "(product_id, source, snapshot_date, stock_quantity, is_simulated) "
                "VALUES (:product_id, :source, :snapshot_date, :stock_quantity, TRUE)"
            ),
            [
                {
                    "product_id": pid,
                    "source": SOURCE,
                    "snapshot_date": snapshot_date,
                    "stock_quantity": int(s),
                }
                for pid, s in zip(product_ids, stock)
            ],
        )
    print(f"simulated stock for {len(product_ids)} products as of {snapshot_date}")


if __name__ == "__main__":
    main()
