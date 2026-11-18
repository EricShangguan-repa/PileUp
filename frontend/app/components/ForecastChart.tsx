"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// Each row has a date plus whichever of `actual` / `predicted` exist that day;
// missing values leave a gap so the two lines only overlap where both exist.
export type ForecastPoint = { date: string; actual?: number; predicted?: number };

export default function ForecastChart({
  points,
  splitDate,
}: {
  points: ForecastPoint[];
  splitDate?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          tickLine={false}
          axisLine={{ stroke: "var(--border)" }}
          minTickGap={40}
        />
        <YAxis
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            color: "var(--text)",
          }}
          formatter={(value: number, name: string) => [
            `${value.toLocaleString("en-GB", { maximumFractionDigits: 2 })} units`,
            name,
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: 13 }}
          formatter={(name: string) => (
            <span style={{ color: "var(--text-secondary)" }}>{name}</span>
          )}
        />
        {splitDate && (
          <ReferenceLine
            x={splitDate}
            stroke="var(--text-muted)"
            strokeDasharray="4 4"
            label={{
              value: "forecast made",
              position: "insideTopRight",
              fill: "var(--text-muted)",
              fontSize: 12,
            }}
          />
        )}
        <Line
          name="Actual units sold"
          dataKey="actual"
          stroke="var(--series-1)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
          connectNulls={false}
          isAnimationActive={false}
        />
        <Line
          name="Forecast"
          dataKey="predicted"
          stroke="var(--series-2)"
          strokeWidth={2}
          strokeDasharray="6 3"
          dot={false}
          activeDot={{ r: 4 }}
          connectNulls={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
