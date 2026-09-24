"use client";

import { useState } from "react";

import type { Row } from "../lib/api";

const PAGE_SIZE = 20;

function cellText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

export default function DataTable({ rows }: { rows: Row[] }) {
  const [page, setPage] = useState(0);

  if (rows.length === 0) {
    return <p className="text-sm text-gray-500">No rows returned.</p>;
  }

  const columns = Object.keys(rows[0]);
  const pageCount = Math.ceil(rows.length / PAGE_SIZE);
  const start = page * PAGE_SIZE;
  const pageRows = rows.slice(start, start + PAGE_SIZE);

  return (
    <div>
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((c) => (
                <th
                  key={c}
                  className="border-b border-gray-200 px-3 py-2 text-left font-semibold text-gray-700"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => (
              <tr key={start + i} className="border-b border-gray-100 last:border-0">
                {columns.map((c) => (
                  <td key={c} className="px-3 py-1.5 whitespace-nowrap">
                    {cellText(row[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pageCount > 1 && (
        <div className="mt-2 flex items-center justify-between text-sm text-gray-600">
          <span>
            Rows {start + 1}-{Math.min(start + PAGE_SIZE, rows.length)} of {rows.length}
          </span>
          <div className="flex items-center gap-3">
            <button
              className="rounded border border-gray-300 px-2 py-1 disabled:opacity-40"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Prev
            </button>
            <span>
              {page + 1} / {pageCount}
            </span>
            <button
              className="rounded border border-gray-300 px-2 py-1 disabled:opacity-40"
              disabled={page >= pageCount - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
