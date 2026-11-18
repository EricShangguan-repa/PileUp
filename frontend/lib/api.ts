// Types mirror the JSON returned by backend/app/routes/*.py.

export type Source = "online_retail" | "shopify";

export type AtRiskProduct = {
  product_id: number;
  source: Source;
  sku: string | null;
  description: string;
  current_stock: number;
  stock_is_simulated: boolean;
  snapshot_date: string;
  forecast_made_date: string;
  forecast_daily_demand: number;
  days_to_stockout: number;
};

export type AtRiskResponse = {
  threshold_days: number;
  source: Source | null;
  products: AtRiskProduct[];
};

export type SalesSummary = {
  source: Source;
  total_revenue: number;
  total_units: number;
  total_orders: number;
  first_day: string | null;
  last_day: string | null;
  weekly: { week_start: string; revenue: number; units: number }[];
};

export type ProductForecast = {
  product_id: number;
  sku: string | null;
  description: string;
  model: string;
  forecast_made_date: string;
  forecast: { date: string; predicted: number }[];
  history: { date: string; units: number }[];
  latest_backtest_fold: { date: string; predicted: number; actual: number }[];
};

export type BacktestSummary = {
  n_products: number;
  n_folds: number;
  horizon_days: number;
  first_eval_day: string;
  last_eval_day: string;
  best_model: string;
  models: { model: string; wape: number; mae: number; wape_28d_total: number }[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Returns null on 404 so pages can show Next's not-found page; anything else
// is a real failure and should surface as an error.
async function get<T>(path: string): Promise<T | null> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET ${path} failed with ${res.status}`);
  return res.json() as Promise<T>;
}

async function getOrThrow<T>(path: string): Promise<T> {
  const body = await get<T>(path);
  if (body === null) throw new Error(`GET ${path} returned 404`);
  return body;
}

export function getAtRisk(source: Source, thresholdDays = 14) {
  return getOrThrow<AtRiskResponse>(
    `/products/at-risk?source=${source}&threshold_days=${thresholdDays}`,
  );
}

export function getSalesSummary(source: Source) {
  return getOrThrow<SalesSummary>(`/sales/summary?source=${source}`);
}

export function getBacktestSummary() {
  return get<BacktestSummary>("/backtest/summary");
}

export function getForecast(productId: number) {
  return get<ProductForecast>(`/forecast/${productId}`);
}

// The UK data is in pounds. The Shopify dev store's currency isn't returned by
// the API, so it's labelled generically rather than guessed.
export const SOURCE_INFO: Record<Source, { label: string; currency: string | null }> = {
  online_retail: { label: "Online Retail II (UK)", currency: "GBP" },
  shopify: { label: "Shopify dev store", currency: null },
};

export function formatMoney(amount: number, source: Source) {
  const { currency } = SOURCE_INFO[source];
  const number = amount.toLocaleString("en-GB", { maximumFractionDigits: 0 });
  return currency ? `£${number}` : `${number} (store currency)`;
}
