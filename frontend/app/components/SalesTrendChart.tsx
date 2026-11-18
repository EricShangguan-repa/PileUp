"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Week = { week_start: string; revenue: number; units: number };

export default function SalesTrendChart({
  weeks,
  currencyLabel,
}: {
  weeks: Week[];
  currencyLabel: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={weeks} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis
          dataKey="week_start"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          tickLine={false}
          axisLine={{ stroke: "var(--border)" }}
          minTickGap={40}
        />
        <YAxis
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => v.toLocaleString("en-GB", { notation: "compact" })}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            color: "var(--text)",
          }}
          labelFormatter={(week) => `Week of ${week}`}
          formatter={(value: number) => [
            `${value.toLocaleString("en-GB", { maximumFractionDigits: 0 })} ${currencyLabel}`,
            "Revenue",
          ]}
        />
        <Line
          type="linear"
          dataKey="revenue"
          stroke="var(--series-1)"
          strokeWidth={2}
          // with only a handful of weeks (the Shopify sample) the points matter
          dot={weeks.length <= 20 ? { r: 4, fill: "var(--series-1)" } : false}
          activeDot={{ r: 4 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
