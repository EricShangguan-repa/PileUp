"""API tests against the local MySQL database. They need the pipeline to have run
(load_online_retail, aggregate_daily_sales, forecast.backtest, simulate_inventory)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app

client = TestClient(app)


def _forecast_product_id() -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT MIN(product_id) FROM forecasts")).scalar_one()


def test_at_risk_products_are_below_threshold_and_marked_simulated():
    response = client.get("/products/at-risk", params={"threshold_days": 14})
    assert response.status_code == 200
    body = response.json()
    assert body["threshold_days"] == 14
    assert body["products"], "expected some at-risk products with the simulated stock"
    for p in body["products"]:
        assert p["days_to_stockout"] < 14
        assert p["stock_is_simulated"] is True
    days = [p["days_to_stockout"] for p in body["products"]]
    assert days == sorted(days)


def test_at_risk_rejects_invalid_threshold():
    assert (
        client.get("/products/at-risk", params={"threshold_days": 0}).status_code == 422
    )


def test_sales_summary():
    response = client.get("/sales/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_revenue"] > 0
    assert body["total_orders"] > 0
    assert body["weekly"]
    assert sum(w["revenue"] for w in body["weekly"]) == pytest.approx(
        body["total_revenue"]
    )


def test_forecast_for_known_product():
    response = client.get(f"/forecast/{_forecast_product_id()}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["forecast"]) == 28
    assert len(body["latest_backtest_fold"]) == 28
    assert body["history"]


def test_forecast_unknown_product_is_404():
    assert client.get("/forecast/999999999").status_code == 404


def test_forecast_product_without_forecast_is_404():
    with engine.connect() as conn:
        product_id = conn.execute(
            text(
                "SELECT MIN(id) FROM products "
                "WHERE id NOT IN (SELECT DISTINCT product_id FROM forecasts)"
            )
        ).scalar_one()
    assert client.get(f"/forecast/{product_id}").status_code == 404


def test_backtest_summary():
    response = client.get("/backtest/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["horizon_days"] == 28
    assert {m["model"] for m in body["models"]} >= {"naive", "moving_average_28"}
