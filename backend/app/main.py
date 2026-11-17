from fastapi import FastAPI

from app.routes import backtest, forecast, products, sales

app = FastAPI(title="PileUp API")
app.include_router(products.router)
app.include_router(sales.router)
app.include_router(forecast.router)
app.include_router(backtest.router)
