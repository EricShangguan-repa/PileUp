from fastapi import APIRouter
from sqlalchemy import text

from app.db import engine

router = APIRouter()


@router.get("/sales/summary")
def sales_summary() -> dict:
    with engine.connect() as conn:
        totals = conn.execute(
            text(
                "SELECT SUM(revenue), SUM(quantity_sold), MIN(sale_date), MAX(sale_date) "
                "FROM daily_sales"
            )
        ).one()
        n_orders = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar_one()
        weekly = conn.execute(
            text(
                "SELECT DATE_SUB(sale_date, INTERVAL WEEKDAY(sale_date) DAY) AS week_start, "
                "SUM(revenue), SUM(quantity_sold) "
                "FROM daily_sales GROUP BY week_start ORDER BY week_start"
            )
        ).all()

    return {
        "total_revenue": float(totals[0]),
        "total_units": int(totals[1]),
        "total_orders": n_orders,
        "first_day": str(totals[2]),
        "last_day": str(totals[3]),
        "weekly": [
            {"week_start": str(w[0]), "revenue": float(w[1]), "units": int(w[2])}
            for w in weekly
        ],
    }
