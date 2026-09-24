"use client";

import type { ReactElement } from "react";
import { useState } from "react";

import type { Row } from "../lib/api";
import BarChart from "./charts/BarChart";
import LineChart from "./charts/LineChart";
import PieChart from "./charts/PieChart";
import ScatterChart from "./charts/ScatterChart";
import type { ChartProps } from "./charts/BarChart";

const CHART_TYPES = ["Bar", "Line", "Pie", "Scatter"] as const;
type ChartType = (typeof CHART_TYPES)[number];

const CHART_COMPONENTS: Record<ChartType, (props: ChartProps) => ReactElement> = {
  Bar: BarChart,
  Line: LineChart,
  Pie: PieChart,
  Scatter: ScatterChart,
};

const selectClass = "rounded border border-gray-300 px-2 py-1 text-sm";

function isNumeric(value: unknown): boolean {
  if (typeof value === "number") return true;
  if (typeof value !== "string" || value.trim() === "") return false;
  return !Number.isNaN(Number(value));
}

export default function ChartPanel({ rows }: { rows: Row[] }) {
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
  // A client-side echo of the task's optional "suggest a default chart" idea: no
  // backend change needed, since the columns already tell us enough — pick the
  // first numeric column as Y (falls back to the second column if none is
  // numeric), the first column as X, and Bar as a safe default chart type.
  const numericColumns = columns.filter((c) => rows.every((r) => isNumeric(r[c])));

  const [chartType, setChartType] = useState<ChartType>("Bar");
  const [xCol, setXCol] = useState(columns[0] ?? "");
  const [yCol, setYCol] = useState(numericColumns[0] ?? columns[1] ?? columns[0] ?? "");

  if (rows.length === 0 || columns.length === 0) {
    return <p className="text-sm text-gray-500">No data to chart.</p>;
  }

  // The chart components expect plain string|number cells; coerce everything else.
  const data = rows.map((row) => {
    const out: Record<string, string | number> = {};
    for (const c of columns) {
      const v = row[c];
      out[c] = typeof v === "number" ? v : v === null || v === undefined ? "" : String(v);
    }
    return out;
  });

  const ChartComponent = CHART_COMPONENTS[chartType];

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2">
          Type
          <select
            className={selectClass}
            value={chartType}
            onChange={(e) => setChartType(e.target.value as ChartType)}
          >
            {CHART_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          X
          <select className={selectClass} value={xCol} onChange={(e) => setXCol(e.target.value)}>
            {columns.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          Y
          <select className={selectClass} value={yCol} onChange={(e) => setYCol(e.target.value)}>
            {columns.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>

      {xCol && yCol ? (
        <ChartComponent data={data} x={xCol} y={yCol} />
      ) : (
        <p className="text-sm text-gray-500">Pick X and Y columns.</p>
      )}
    </div>
  );
}
