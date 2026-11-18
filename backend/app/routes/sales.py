from typing import Literal

from fastapi import APIRouter
from sqlalchemy import text

from app.db import engine

router = APIRouter()


@router.get("/sales/summary")
def sales_summary(
    source: Literal["online_retail", "shopify"] = "online_retail",
) -> dict:
    """Totals and weekly trend for one source; sources aren't mixed because their
    revenue is in different currencies."""
    params = {"source": source}
    with engine.connect() as conn:
        totals = conn.execute(
            text(
                "SELECT COALESCE(SUM(revenue), 0), COALESCE(SUM(quantity_sold), 0), "
                "MIN(sale_date), MAX(sale_date) FROM daily_sales WHERE source = :source"
            ),
            params,
        ).one()
        n_orders = conn.execute(
            text(
                "SELECT COUNT(*) FROM orders WHERE source = :source AND NOT is_cancelled"
            ),
            params,
        ).scalar_one()
        weekly = conn.execute(
            text(
                "SELECT DATE_SUB(sale_date, INTERVAL WEEKDAY(sale_date) DAY) AS week_start, "
                "SUM(revenue), SUM(quantity_sold) FROM daily_sales "
                "WHERE source = :source GROUP BY week_start ORDER BY week_start"
            ),
            params,
        ).all()

    return {
        "source": source,
        "total_revenue": float(totals[0]),
        "total_units": int(totals[1]),
        "total_orders": n_orders,
        "first_day": str(totals[2]) if totals[2] else None,
        "last_day": str(totals[3]) if totals[3] else None,
        "weekly": [
            {"week_start": str(w[0]), "revenue": float(w[1]), "units": int(w[2])}
            for w in weekly
        ],
    }
