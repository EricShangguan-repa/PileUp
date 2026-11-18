# CLAUDE.md: Shopify Store Insights

A full-stack software + data project. It syncs a Shopify store's orders and products into MySQL, cleans and transforms the data, forecasts per-product demand and days until stockout, serves the results through a FastAPI REST API, and shows them in a Next.js dashboard.

This file guides Claude Code, the AI coding assistant used on this project. It sets the conventions, testing rules and build order the assistant must follow. Finished and honest beats ambitious and half-built.

Personal, machine-specific notes live in a git-ignored file, imported here when present:
@CLAUDE.private.md

---

## Part 1: How to work (behavioural rules)

*Adapted from forrestchang/andrej-karpathy-skills. These rules favour caution over speed; use judgment on trivial tasks.*

### 1. Think before coding
- State your assumptions before writing code. If a request has more than one reasonable reading, list them; don't silently pick one.
- If a simpler approach exists than the one asked for, say so before building.
- If something is unclear, stop and ask. Don't hide confusion, and surface tradeoffs plainly.

### 2. Simplicity first
- Write the minimum code that solves the actual problem. If 200 lines could be 50, rewrite it.
- No speculative features, single-use abstractions, unrequested config options, or error handling for cases that can't happen.
- A weekend project needs no plugin systems, no generic "data source" frameworks, and no microservices.

### 3. Surgical changes
- Touch only what the task needs. Match the existing style, even if you'd write it differently.
- Don't refactor working code you weren't asked to change. If you spot dead or bad code elsewhere, mention it; don't fix it.
- Remove only the imports, functions, or files that *your* change made unused.

### 4. Goal-driven execution
- Turn every task into a verifiable goal before starting. Example: "the `/forecast/{id}` endpoint returns 200 with a 28-day forecast, and its test passes."
- For bugs: write a failing test that reproduces it, then fix it.
- For multi-step work: give a short plan where each step has a check, then loop until the checks pass. Don't call something done until you've run it.

---

## Part 2: Project specifics

### Architecture

```
Data sources                Storage          Data layer               Serving             UI
------------                -------          ----------               -------             --
Online Retail II (UCI) ──┐
  real history, bulk     ├─> MySQL ──> clean/transform (pandas) ──> FastAPI REST ──> Next.js dashboard
Shopify dev store ───────┘   (one     ──> forecast + backtest
  live sync, small sample     schema)
```

**Two data sources, one schema. This is deliberate:**
- **Online Retail II** (UCI, real transactions) is the *forecasting and backtesting* dataset. It's real history from a UK online gift retailer, Dec 2009 – Dec 2011, about 1.07M invoice lines. License CC BY 4.0. Credit: Chen, D. (2012), Online Retail II, UCI ML Repository, DOI 10.24432/C5CG6D.
- **Shopify dev store** proves the live *integration*: a GraphQL Admin API sync with pagination, rate limits, and incremental updates. It holds only a small sample, because dev stores limit order creation (see Gotchas).
- Both loaders write to the **same tables**, so everything downstream (transforms, forecast, API, UI) works the same on either source. A `source` column tells them apart.

### Tech stack
- **Backend/data:** Python 3.12, FastAPI, pandas, NumPy, SQLAlchemy Core (plain SQL is fine), PyMySQL, openpyxl (reads the directly downloaded xlsx), `httpx` for the Shopify GraphQL calls
- **Database:** MySQL 8
- **Frontend:** Next.js (App Router, TypeScript), one or two pages, a simple chart library
- **Testing/quality:** pytest, ruff (lint + format)
- **Repo layout:**
  ```
  backend/
    app/            # FastAPI app: main.py, routes/, db.py
    pipeline/       # load_online_retail.py, sync_shopify.py, transform.py
    forecast/       # models.py (baselines), backtest.py
    tests/
  frontend/         # Next.js app
  data/raw/         # downloaded datasets (git-ignored)
  docs/             # architecture diagram, backtest results
  ```

### Commands
*All of these are real. Keep this accurate.*

```bash
# Backend setup
cd backend
python -m venv .venv
source .venv/Scripts/activate        # Git Bash on Windows (PowerShell: .venv\Scripts\Activate.ps1)
pip install -r requirements.txt

# Database
mysql -u root -p < schema.sql        # create tables

# MySQL 8 must be running locally; credentials come from DATABASE_URL in .env

# Data pipeline (xlsx must be at data/raw/online_retail_II.xlsx, from
# https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip; ucimlrepo can't import this dataset)
python -m pipeline.load_online_retail   # clean + load real history (~80s)
python -m pipeline.seed_shopify_demand # ONE-TIME: 326 synthetic test orders shaped on real UK demand + test stock (~70 min, resumable)
                                        # (replaces the earlier random seed_shopify orders, which it deletes)
python -m pipeline.sync_shopify         # dev store -> MySQL: variants, store stock, orders (incremental)
python -m pipeline.sync_shopify --full  # wipe synced Shopify rows (not products) and resync; needed after deleting orders
python -m pipeline.aggregate_daily_sales  # order_lines -> daily_sales for both sources (~65s); rerun after a sync
python -m forecast.backtest             # rolling-origin backtest -> docs/backtest_results.md + .json, best model's forecasts -> forecasts table (~15s)
python -m pipeline.simulate_inventory   # SIMULATED stock for forecast products (run after backtest)
python -m forecast.forecast_shopify     # 28-day Shopify forecasts with the backtest's best model (after aggregate)

# API
uvicorn app.main:app --reload           # http://localhost:8000/docs

# Tests and lint
pytest                                  # full suite (test_api.py needs MySQL running + pipeline already run)
pytest tests/test_transform.py -q       # single file
ruff check . && ruff format .

# Frontend (needs the API running; fetches happen server-side, so no CORS setup)
cd frontend
npm install
cp .env.local.example .env.local         # NEXT_PUBLIC_API_URL, defaults to http://localhost:8000
npm run dev                              # http://localhost:3000
npm run lint && npm run build            # checks before committing frontend changes
```

### Conventions
- **Python:** type hints on public functions, small pure functions in `pipeline/` and `forecast/` so they're easy to test, snake_case, no classes unless state really needs one.
- **SQL:** parameterized queries only. Tables: `products`, `orders`, `order_lines`, `inventory_snapshots`, `daily_sales`, `forecasts`. Every row has a `source` column (`online_retail` | `shopify`).
- **Dates:** store UTC timestamps. Aggregate to daily sales per product, with explicit zero-fill for days with no sales.
- **API:** REST, JSON, plain nouns. Endpoints: `GET /products/at-risk`, `GET /sales/summary`, `GET /forecast/{product_id}`, `GET /backtest/summary`. Return 404 for unknown IDs, not 500.
- **Errors:** fail loudly in pipeline scripts (log + exit non-zero). In the API, handle only errors that can actually happen.
- **Frontend:** TypeScript, fetch from the FastAPI base URL in an env var, no state library.
- **Commits:** small and descriptive. One logical change per commit.

### Forecast and evaluation (how success is measured)
- **Use a rolling-origin backtest, NOT a random train/test split.** A random split leaks future sales into training and inflates accuracy. Time series must be split by time.
  - Expanding window: train on all history before a cutoff, forecast the next **28 days**, step the cutoff forward **7 days**, repeat across the last ~6 months of data.
  - A single time-based holdout (train up to date X, test after X) is the minimum. Rolling-origin is the target.
- **Models, simplest first:**
  1. Naive (repeat the last day)
  2. Seasonal naive (repeat the same weekday from last week)
  3. Moving average (7- and 28-day)
  4. Only if time allows: one ML model (e.g. gradient boosting on lag and day-of-week features), and keep it only if it beats the baselines.
- **Metrics:** MAE and **WAPE** (sum of |error| / sum of actual). **Don't use MAPE.** Daily product sales have many zeros, which break it.
- **Scope:** forecast the top ~50 products by revenue. The long tail is too sparse to be meaningful.
- **Report:** write results to `docs/backtest_results.md`: per-model WAPE and MAE, number of products, number of folds, horizon, date range. Any accuracy number reported anywhere comes ONLY from this file.
- **Stockout logic:** days_to_stockout = current_stock / forecast daily demand. Flag a product if it's below the reorder threshold (default 14 days).

### Gotchas
- **Online Retail II has dirty data. Clean it explicitly, and test each rule:**
  - Invoices starting with `C` are cancellations (negative quantities). Exclude them from demand, or net them out, and document which.
  - Non-product stock codes (`POST`, `D`, `M`, `DOT`, `BANK CHARGES`, `AMAZONFEE`, `C2`, etc.): exclude them.
  - `Price <= 0` and `Quantity <= 0` rows on non-cancelled invoices: exclude them.
  - Decided: cancellations are **excluded**, not netted out.
  - The same StockCode appears in both cases (e.g. `72349B`/`72349b`, 173 codes). MySQL's collation is case-insensitive, so StockCode is uppercased during cleaning.
  - Daily sales are zero-filled only within each product's first-to-last sale window.
  - Missing `Customer ID` is common. That's fine for demand forecasting; don't drop those rows for that reason.
  - Big wholesale orders create spikes. Note them; don't silently clip them.
  - The data is UK-based with strong Nov–Dec seasonality, and the two years cover that twice.
- **Online Retail II has no inventory levels.** Stock levels for the stockout feature are **simulated**. Say so in the README and the UI. Never present simulated stock as real.
- **Shopify dev store limits:**
  - Order creation through the API is capped at about **5 orders/minute** on development stores, per Shopify's REST docs. Community reports suggest a total order cap too (unverified).
  - So seed the dev store with a *small* sample (≈20 products, a few dozen orders). Never try to replay the full dataset into Shopify.
  - The Admin GraphQL API is rate limited by query cost. Respect the throttle info in the response and back off when throttled.
  - Paginate with cursors (`pageInfo.hasNextPage`, `endCursor`).
  - Make the sync incremental: fetch only orders updated since the last sync timestamp (stored in `sync_state`).
  - The sync doesn't detect deletions (deleted orders never match the updated_at query). After deleting orders in the store, run `sync_shopify --full`.
  - Without the `read_all_orders` permission, Shopify only returns orders from the last 60 days. The demand seed is backdated to 2026-09-21, so a full resync after about 2026-11-20 may miss the oldest orders (unverified whether the cutoff uses processedAt or creation time); incremental syncs keep what's already in MySQL.
  - Auth: the app lives in Shopify's Dev Dashboard. There is no permanent `shpat_` token; `shopify_client.py` gets a 24h token with the client credentials grant (client ID + secret).
  - Reading orders needs the app set to **custom distribution**; before that, Shopify blocks the Order object as protected customer data.
  - Each Shopify **variant** is one PileUp product (variants are what Shopify sells and stocks, like StockCodes).
  - Shopify stock comes from the store (`is_simulated = FALSE`), but it is **test-store stock set by `seed_shopify_demand`** (5-40 days of demand), not a real merchant's inventory. Online Retail stock is simulated.
  - Shopify orders are **synthetic test orders**: 56 days of real UK demand (2011-09-12 to 2011-11-06, top 15 products, scaled to 0.5-2 units/day) replayed onto 2026-09-21 to 2026-11-15. Never report forecast accuracy on Shopify data; accuracy numbers come only from the UK backtest.
  - Revenue is in different currencies per source (GBP vs the store's currency), so never sum across sources.
- **Frontend:** Recharts 2 needs `react-is` overridden to the React 19 version (`overrides` in `frontend/package.json`); keep them in step when upgrading React. Chart components must be client components (`"use client"`).
- **Secrets:** `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `DATABASE_URL`, `NEXT_PUBLIC_API_URL` go in `.env` (git-ignored). Commit a `.env.example` with placeholders only. Never print or commit tokens.
- **Don't commit:** `data/raw/`, `.env`, `.venv/`, `node_modules/`, or the 43 MB xlsx.
- **Windows:** use the Git Bash or PowerShell syntax noted in Commands.
- **Honesty rules:**
  - Never invent metrics, users, or results. Synthetic or simulated data must be labelled as such.

### Workflow
- **Stay inside this project folder.** Don't create, edit or delete anything outside it without asking first.
- **Before saying a task is done:** run it, run `pytest`, and run `ruff check .`. Show the output, or say plainly what wasn't verified.
- **Keep changes small:** one feature or fix per change, ideally under ~200 lines of diff. Ask before anything bigger.
- **Build order (don't skip ahead):**
  1. Load and clean Online Retail II into MySQL, with tests for each cleaning rule.
  2. Aggregate daily sales per product.
  3. Baseline forecasts + rolling-origin backtest → `docs/backtest_results.md`.
  4. FastAPI endpoints + tests.
  5. Shopify dev store: seed a small sample, then build the GraphQL sync into the same schema.
  6. Next.js dashboard: at-risk products, a sales trend, a forecast vs actual chart.
  7. README: what it is, why, architecture diagram, backtest results, data sources + license credit, simulated-data disclaimer, how to run.
- **Time box:** if a step blows up, cut scope (fewer products, simpler UI) instead of slipping the target date. Steps 1–4 + README are the minimum shippable project.
- **Update this file:** when a command changes, or when Claude makes the same mistake twice, add it to Commands or Gotchas.
