"""28-day forecasts for Shopify variants with the best model from the UK backtest.

The Shopify orders are synthetic test orders, so no accuracy is measured here:
the model choice comes from the real-data backtest (docs/backtest_results.json).
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.db import engine
from forecast.backtest import HORIZON, full_series
from forecast.models import MODELS

SOURCE = "shopify"
RESULTS_PATH = Path(__file__).resolve().parents[2] / "docs" / "backtest_results.json"


def future_rows(
    sales: pd.DataFrame, last_day, model_name: str, horizon: int
) -> list[dict]:
    """Forecast `horizon` days after `last_day` for every product in `sales`."""
    rows = []
    for product_id, product_sales in sales.groupby("product_id"):
        series = full_series(product_sales, last_day)
        predicted = MODELS[model_name](series.to_numpy(), horizon)
        rows += [
            {
                "product_id": int(product_id),
                "source": SOURCE,
                "forecast_made_date": last_day,
                "horizon_date": last_day + timedelta(days=i),
                "predicted_quantity": round(float(p), 2),
                "model_name": model_name,
            }
            for i, p in enumerate(predicted, start=1)
        ]
    return rows


def main() -> None:
    model_name = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))["best_model"]
    last_day = datetime.now(UTC).date() - timedelta(days=1)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT product_id, sale_date, quantity_sold FROM daily_sales "
                "WHERE source = :source"
            ),
            {"source": SOURCE},
        ).all()
    sales = pd.DataFrame(rows, columns=["product_id", "sale_date", "quantity_sold"])
    if sales.empty:
        raise SystemExit("no Shopify daily sales; run sync_shopify and aggregate first")

    records = future_rows(sales, last_day, model_name, HORIZON)
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM forecasts WHERE source = :source"), {"source": SOURCE}
        )
        conn.execute(
            text(
                "INSERT INTO forecasts (product_id, source, forecast_made_date, horizon_date, "
                "predicted_quantity, model_name) VALUES (:product_id, :source, "
                ":forecast_made_date, :horizon_date, :predicted_quantity, :model_name)"
            ),
            records,
        )
    print(
        f"saved {len(records)} {model_name} forecast rows for "
        f"{sales['product_id'].nunique()} Shopify products, made {last_day}"
    )


if __name__ == "__main__":
    main()
