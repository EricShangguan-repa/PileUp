import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

RESULTS_PATH = Path(__file__).resolve().parents[3] / "docs" / "backtest_results.json"


@router.get("/backtest/summary")
def backtest_summary() -> dict:
    if not RESULTS_PATH.exists():
        raise HTTPException(
            404, "No backtest results yet. Run: python -m forecast.backtest"
        )
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
