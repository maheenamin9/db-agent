"use client";

import { Pie, PieChart as RPieChart, Tooltip } from "recharts";

import type { ChartProps } from "./BarChart";

// `x` is the label column, `y` the value column.
export default function PieChart({ data, x, y, width = 600, height = 320 }: ChartProps) {
  return (
    <RPieChart width={width} height={height}>
      <Pie data={data} nameKey={x} dataKey={y} fill="#4f46e5" label />
      <Tooltip />
    </RPieChart>
  );
}
