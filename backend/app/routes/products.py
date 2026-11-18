from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.db import engine
from forecast.models import days_to_stockout

router = APIRouter()


@router.get("/products/at-risk")
def at_risk_products(
    threshold_days: int = Query(14, ge=1),
    source: Literal["online_retail", "shopify"] | None = None,
) -> dict:
    """Products whose latest stock runs out within `threshold_days` at their latest
    forecast demand. Online Retail stock is simulated; Shopify stock is the store's."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT p.id, p.source, p.sku, p.description, i.stock_quantity, "
                "i.is_simulated, i.snapshot_date, lf.made AS forecast_made_date, "
                "AVG(f.predicted_quantity) AS daily_demand "
                "FROM inventory_snapshots i "
                "JOIN (SELECT product_id, MAX(snapshot_date) AS latest "
                "      FROM inventory_snapshots GROUP BY product_id) li "
                "  ON li.product_id = i.product_id AND li.latest = i.snapshot_date "
                "JOIN (SELECT product_id, MAX(forecast_made_date) AS made "
                "      FROM forecasts GROUP BY product_id) lf "
                "  ON lf.product_id = i.product_id "
                "JOIN forecasts f ON f.product_id = i.product_id "
                "  AND f.forecast_made_date = lf.made AND f.horizon_date > lf.made "
                "JOIN products p ON p.id = i.product_id "
                "WHERE (:source IS NULL OR p.source = :source) "
                "GROUP BY p.id, p.source, p.sku, p.description, i.stock_quantity, "
                "i.is_simulated, i.snapshot_date, lf.made"
            ),
            {"source": source},
        ).all()

    products = []
    for r in rows:
        demand = float(r.daily_demand)
        days = days_to_stockout(r.stock_quantity, demand)
        if days is not None and days < threshold_days:
            products.append(
                {
                    "product_id": r.id,
                    "source": r.source,
                    "sku": r.sku,
                    "description": r.description,
                    "current_stock": r.stock_quantity,
                    "stock_is_simulated": bool(r.is_simulated),
                    "snapshot_date": str(r.snapshot_date),
                    "forecast_made_date": str(r.forecast_made_date),
                    "forecast_daily_demand": round(demand, 2),
                    "days_to_stockout": round(days, 1),
                }
            )
    products.sort(key=lambda p: p["days_to_stockout"])
    return {"threshold_days": threshold_days, "source": source, "products": products}
