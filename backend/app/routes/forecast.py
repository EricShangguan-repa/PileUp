from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db import engine

router = APIRouter()

HISTORY_DAYS = 56


@router.get("/forecast/{product_id}")
def product_forecast(product_id: int) -> dict:
    """Next-28-day forecast, recent history, and the latest backtest fold (forecast vs actual)."""
    with engine.connect() as conn:
        product = conn.execute(
            text("SELECT id, sku, description FROM products WHERE id = :id"),
            {"id": product_id},
        ).one_or_none()
        if product is None:
            raise HTTPException(404, f"Product {product_id} not found")

        made_dates = conn.execute(
            text(
                "SELECT DISTINCT forecast_made_date FROM forecasts "
                "WHERE product_id = :id ORDER BY forecast_made_date DESC LIMIT 2"
            ),
            {"id": product_id},
        ).all()
        if not made_dates:
            raise HTTPException(404, f"No forecast for product {product_id}")
        latest_made = made_dates[0][0]

        future = conn.execute(
            text(
                "SELECT horizon_date, predicted_quantity, model_name FROM forecasts "
                "WHERE product_id = :id AND forecast_made_date = :made ORDER BY horizon_date"
            ),
            {"id": product_id, "made": latest_made},
        ).all()
        history = conn.execute(
            text(
                "SELECT sale_date, quantity_sold FROM daily_sales "
                "WHERE product_id = :id AND sale_date <= :made "
                "AND sale_date > DATE_SUB(:made, INTERVAL :days DAY) ORDER BY sale_date"
            ),
            {"id": product_id, "made": latest_made, "days": HISTORY_DAYS},
        ).all()

        backtest = []
        if len(made_dates) > 1:
            backtest = conn.execute(
                text(
                    "SELECT f.horizon_date, f.predicted_quantity, "
                    "COALESCE(ds.quantity_sold, 0) AS actual "
                    "FROM forecasts f LEFT JOIN daily_sales ds "
                    "ON ds.product_id = f.product_id AND ds.sale_date = f.horizon_date "
                    "WHERE f.product_id = :id AND f.forecast_made_date = :made "
                    "ORDER BY f.horizon_date"
                ),
                {"id": product_id, "made": made_dates[1][0]},
            ).all()

    return {
        "product_id": product.id,
        "sku": product.sku,
        "description": product.description,
        "model": future[0].model_name,
        "forecast_made_date": str(latest_made),
        "forecast": [
            {"date": str(r.horizon_date), "predicted": float(r.predicted_quantity)}
            for r in future
        ],
        "history": [
            {"date": str(r.sale_date), "units": r.quantity_sold} for r in history
        ],
        "latest_backtest_fold": [
            {
                "date": str(r.horizon_date),
                "predicted": float(r.predicted_quantity),
                "actual": int(r.actual),
            }
            for r in backtest
        ],
    }
