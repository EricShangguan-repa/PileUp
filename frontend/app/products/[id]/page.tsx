import Link from "next/link";
import { notFound } from "next/navigation";

import { getForecast } from "@/lib/api";
import ForecastChart, { type ForecastPoint } from "../../components/ForecastChart";

export default async function ProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const productId = Number(id);
  if (!Number.isInteger(productId) || productId <= 0) notFound();

  const data = await getForecast(productId);
  if (!data) notFound();

  const outlook: ForecastPoint[] = [
    ...withZeroDays(data.history, data.forecast_made_date),
    ...data.forecast.map((f) => ({ date: f.date, predicted: f.predicted })),
  ];
  const fold = data.latest_backtest_fold;
  const foldMade = fold.length > 0 ? fold[0].date : null;
  const avgDemand =
    data.forecast.reduce((sum, f) => sum + f.predicted, 0) / data.forecast.length;

  return (
    <>
      <p>
        <Link href="/">← Back to overview</Link>
      </p>
      <h1>{data.description}</h1>
      <p className="muted">
        {data.sku && <>SKU {data.sku} · </>}
        Model {data.model}, forecast made {data.forecast_made_date} · about{" "}
        {avgDemand.toFixed(2)} units/day over the next {data.forecast.length} days
      </p>

      <section className="card">
        <h2>Recent sales and the next {data.forecast.length} days</h2>
        <ForecastChart points={outlook} splitDate={data.forecast_made_date} />
      </section>

      <section className="card">
        <h2>Forecast vs actual</h2>
        {foldMade ? (
          <>
            <p className="muted">
              The most recent backtest fold: what the model predicted for the{" "}
              {fold.length} days from {foldMade}, next to what actually sold.
            </p>
            <ForecastChart
              points={fold.map((f) => ({
                date: f.date,
                actual: f.actual,
                predicted: f.predicted,
              }))}
            />
          </>
        ) : (
          // Shopify products land here: their orders are synthetic, so there's
          // no backtest for them and no accuracy to show.
          <p className="muted">
            No backtest for this product. Its orders are synthetic test orders, so
            forecast accuracy is only measured on the real UK data.
          </p>
        )}
      </section>
    </>
  );
}

// daily_sales stops at a product's last sale, but the forecast treats every day
// after that (up to the day it was made) as zero sales. Shopify products hit this
// because the seeded orders end before today, so draw those days as zeros too.
function withZeroDays(
  history: { date: string; units: number }[],
  madeDate: string,
): ForecastPoint[] {
  const points: ForecastPoint[] = history.map((h) => ({ date: h.date, actual: h.units }));
  if (points.length === 0) return points;
  const day = new Date(`${points[points.length - 1].date}T00:00:00Z`);
  const end = new Date(`${madeDate}T00:00:00Z`);
  for (day.setUTCDate(day.getUTCDate() + 1); day <= end; day.setUTCDate(day.getUTCDate() + 1)) {
    points.push({ date: day.toISOString().slice(0, 10), actual: 0 });
  }
  return points;
}
