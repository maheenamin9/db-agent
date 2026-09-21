"use client";

import { CartesianGrid, Scatter, ScatterChart as RScatterChart, Tooltip, XAxis, YAxis } from "recharts";

import type { ChartProps } from "./BarChart";

export default function ScatterChart({ data, x, y, width = 600, height = 320 }: ChartProps) {
  return (
    <RScatterChart width={width} height={height}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey={x} name={x} />
      <YAxis dataKey={y} name={y} />
      <Tooltip />
      <Scatter data={data} fill="#4f46e5" />
    </RScatterChart>
  );
}
