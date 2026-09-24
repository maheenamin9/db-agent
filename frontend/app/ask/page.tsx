"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type AskResponse } from "../../lib/api";
import ChartPanel from "../../components/ChartPanel";
import DataTable from "../../components/DataTable";
import SqlView from "../../components/SqlView";

const TABS = ["Answer", "SQL", "Table", "Chart"] as const;
type Tab = (typeof TABS)[number];

const buttonClass =
  "rounded bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50";

function errorMessage(e: unknown) {
  return e instanceof ApiError ? e.message : String(e);
}

function useElapsedSeconds(active: boolean) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!active) return;
    setElapsed(0);
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [active]);
  return elapsed;
}

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [tab, setTab] = useState<Tab>("Answer");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const elapsed = useElapsedSeconds(loading);

  const ask = async () => {
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setTab("Answer");
    try {
      setResult(await api.ask(question.trim()));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-semibold mb-1">Ask</h1>
      <p className="text-sm text-gray-600 mb-6">Ask a question about your data in plain English.</p>

      <div className="flex gap-2 mb-2">
        <input
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          placeholder="e.g. What is the total order amount per country?"
          disabled={loading}
        />
        <button className={buttonClass} disabled={loading || !question.trim()} onClick={ask}>
          {loading ? "Thinking…" : "Ask"}
        </button>
      </div>

      {loading && (
        <p className="mb-4 text-sm text-gray-500">
          Thinking… {elapsed}s{" "}
          <span className="text-gray-400">
            (a local model can take anywhere from under a minute to several minutes)
          </span>
        </p>
      )}

      {error && (
        <p className="mb-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}

      {result && (
        <div>
          <div className="flex gap-2 mb-4 border-b border-gray-200">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${
                  tab === t
                    ? "border-gray-900 text-gray-900"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {tab === "Answer" && (
            <div
              className={`rounded border p-4 text-sm ${
                result.error
                  ? "border-amber-200 bg-amber-50 text-amber-900"
                  : "border-gray-200 bg-gray-50 text-gray-800"
              }`}
            >
              {result.answer}
            </div>
          )}

          {tab === "SQL" && <SqlView sql={result.sql} />}

          {tab === "Table" && <DataTable rows={result.rows} />}

          {tab === "Chart" && <ChartPanel rows={result.rows} />}
        </div>
      )}
    </div>
  );
}
