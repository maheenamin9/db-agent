"use client";

import { CartesianGrid, Line, LineChart as RLineChart, Tooltip, XAxis, YAxis } from "recharts";

import type { ChartProps } from "./BarChart";

export default function LineChart({ data, x, y, width = 600, height = 320 }: ChartProps) {
  return (
    <RLineChart width={width} height={height} data={data}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey={x} />
      <YAxis />
      <Tooltip />
      <Line dataKey={y} stroke="#4f46e5" />
    </RLineChart>
  );
}
