import Link from "next/link";

import {
  type Source,
  SOURCE_INFO,
  formatMoney,
  getAtRisk,
  getBacktestSummary,
  getSalesSummary,
} from "@/lib/api";
import SalesTrendChart from "./components/SalesTrendChart";

const THRESHOLD_DAYS = 14;

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

export default async function Dashboard({
  searchParams,
}: {
  searchParams: Promise<{ source?: string }>;
}) {
  const { source: requested } = await searchParams;
  const source: Source = requested === "shopify" ? "shopify" : "online_retail";

  const [atRisk, sales, backtest] = await Promise.all([
    getAtRisk(source, THRESHOLD_DAYS),
    getSalesSummary(source),
    source === "online_retail" ? getBacktestSummary() : Promise.resolve(null),
  ]);

  return (
    <>
      <h1>Store overview</h1>
      <p className="muted">
        One data source at a time. Revenue is in a different currency per source,
        so the two are never added together.
      </p>

      <nav className="tabs">
        {(Object.keys(SOURCE_INFO) as Source[]).map((s) => (
          <Link
            key={s}
            href={`/?source=${s}`}
            className="tab"
            aria-current={s === source ? "page" : undefined}
          >
            {SOURCE_INFO[s].label}
          </Link>
        ))}
      </nav>

      {source === "online_retail" ? (
        <p className="note">
          Real UK sales history (Dec 2009 – Dec 2011). This dataset has no
          inventory, so the stock levels below are <strong>simulated</strong>.
        </p>
      ) : (
        <p className="note">
          The Shopify orders are <strong>synthetic test orders</strong> shaped on
          real UK demand, and stock is test-store stock set by the seeding script.
          They show the live integration, not a real merchant&apos;s sales.
        </p>
      )}

      <section className="card">
        <h2>At risk of stocking out within {THRESHOLD_DAYS} days</h2>
        {atRisk.products.length === 0 ? (
          <p className="muted">No products are at risk right now.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th className="num">Stock</th>
                  <th>Stock type</th>
                  <th className="num">Forecast units/day</th>
                  <th className="num">Days to stockout</th>
                </tr>
              </thead>
              <tbody>
                {atRisk.products.map((p) => (
                  <tr key={p.product_id}>
                    <td>
                      <Link href={`/products/${p.product_id}`}>{p.description}</Link>
                      {p.sku && <span className="muted"> · {p.sku}</span>}
                    </td>
                    <td className="num">{p.current_stock}</td>
                    <td>
                      {p.stock_is_simulated ? (
                        <span className="badge badge-simulated">Simulated stock</span>
                      ) : (
                        <span className="badge badge-store">Test-store stock</span>
                      )}
                    </td>
                    <td className="num">{p.forecast_daily_demand}</td>
                    <td className="num">{p.days_to_stockout}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Weekly revenue</h2>
        <div className="stats">
          <Stat label="Revenue" value={formatMoney(sales.total_revenue, source)} />
          <Stat label="Orders" value={sales.total_orders.toLocaleString("en-GB")} />
          <Stat label="Units" value={sales.total_units.toLocaleString("en-GB")} />
          <Stat label="Dates" value={`${sales.first_day} → ${sales.last_day}`} />
        </div>
        <SalesTrendChart
          weeks={sales.weekly}
          currencyLabel={SOURCE_INFO[source].currency ?? "(store currency)"}
        />
      </section>

      {backtest && (
        <section className="card">
          <h2>Backtest accuracy</h2>
          <p className="muted">
            Rolling-origin backtest on the UK data: {backtest.n_folds} folds,{" "}
            {backtest.horizon_days}-day horizon, top {backtest.n_products} products,
            evaluated {backtest.first_eval_day} to {backtest.last_eval_day}. Lower
            WAPE is better.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th className="num">Daily WAPE</th>
                  <th className="num">Daily MAE (units)</th>
                  <th className="num">28-day total WAPE</th>
                </tr>
              </thead>
              <tbody>
                {backtest.models.map((m) => (
                  <tr key={m.model}>
                    <td>
                      {m.model}
                      {m.model === backtest.best_model && (
                        <span className="muted"> (used for forecasts)</span>
                      )}
                    </td>
                    <td className="num">{pct(m.wape)}</td>
                    <td className="num">{m.mae.toFixed(2)}</td>
                    <td className="num">{pct(m.wape_28d_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
