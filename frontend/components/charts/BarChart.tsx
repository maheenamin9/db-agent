"use client";

import { Bar, BarChart as RBarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

export type ChartProps = {
  data: Record<string, string | number>[];
  x: string;
  y: string;
  width?: number;
  height?: number;
};

export default function BarChart({ data, x, y, width = 600, height = 320 }: ChartProps) {
  return (
    <RBarChart width={width} height={height} data={data}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey={x} />
      <YAxis />
      <Tooltip />
      <Bar dataKey={y} fill="#4f46e5" />
    </RBarChart>
  );
}
