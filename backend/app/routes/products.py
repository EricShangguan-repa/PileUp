from fastapi import APIRouter, Query
from sqlalchemy import text

from app.db import engine
from forecast.models import days_to_stockout

router = APIRouter()


@router.get("/products/at-risk")
def at_risk_products(threshold_days: int = Query(14, ge=1)) -> dict:
    """Products whose (simulated) stock runs out within `threshold_days` at forecast demand."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT p.id, p.sku, p.description, i.stock_quantity, i.is_simulated, "
                "i.snapshot_date, AVG(f.predicted_quantity) AS daily_demand "
                "FROM inventory_snapshots i "
                "JOIN products p ON p.id = i.product_id "
                "JOIN forecasts f ON f.product_id = i.product_id "
                "AND f.forecast_made_date = i.snapshot_date "
                "AND f.horizon_date > i.snapshot_date "
                "GROUP BY p.id, p.sku, p.description, i.stock_quantity, i.is_simulated, "
                "i.snapshot_date"
            )
        ).all()

    products = []
    for r in rows:
        demand = float(r.daily_demand)
        days = days_to_stockout(r.stock_quantity, demand)
        if days is not None and days < threshold_days:
            products.append(
                {
                    "product_id": r.id,
                    "sku": r.sku,
                    "description": r.description,
                    "current_stock": r.stock_quantity,
                    "stock_is_simulated": bool(r.is_simulated),
                    "snapshot_date": str(r.snapshot_date),
                    "forecast_daily_demand": round(demand, 2),
                    "days_to_stockout": round(days, 1),
                }
            )
    products.sort(key=lambda p: p["days_to_stockout"])
    return {"threshold_days": threshold_days, "products": products}
