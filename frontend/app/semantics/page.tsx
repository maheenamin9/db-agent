"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type Semantics } from "../../lib/api";
import RelationshipsPanel from "../../components/RelationshipsPanel";

const inputClass =
  "w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-gray-500 focus:outline-none";
const buttonClass =
  "rounded bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50";
const secondaryButtonClass =
  "rounded border border-gray-300 px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50";
const linkButtonClass = "text-sm text-blue-600 hover:underline disabled:opacity-50 disabled:no-underline";

function errorMessage(e: unknown) {
  return e instanceof ApiError ? e.message : String(e);
}

export default function SemanticsPage() {
  const [semantics, setSemantics] = useState<Semantics | null>(null);
  const [savedJson, setSavedJson] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [generating, setGenerating] = useState<Set<string>>(new Set());
  const [generateErrors, setGenerateErrors] = useState<Record<string, string>>({});

  const dirty = semantics !== null && JSON.stringify(semantics) !== savedJson;

  const load = (fetcher: () => Promise<Semantics>) => {
    setLoading(true);
    setError(null);
    fetcher()
      .then((s) => {
        setSemantics(s);
        setSavedJson(JSON.stringify(s));
      })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  };

  // On first load, sync so every real DuckDB table/column shows up even if this is
  // the first visit — sync never overwrites a description already written (Task 7).
  useEffect(() => load(api.syncSemantics), []);

  const refresh = () => {
    if (dirty && !confirm("Discard unsaved changes and reload from disk?")) return;
    load(api.getSemantics);
  };

  const syncFromTables = () => load(api.syncSemantics);

  const setModelDescription = (modelName: string, description: string) => {
    setSemantics((s) =>
      s
        ? {
            ...s,
            models: s.models.map((m) => (m.name === modelName ? { ...m, description } : m)),
          }
        : s
    );
    setSaved(false);
  };

  const setColumnDescription = (modelName: string, columnName: string, description: string) => {
    setSemantics((s) =>
      s
        ? {
            ...s,
            models: s.models.map((m) =>
              m.name === modelName
                ? {
                    ...m,
                    columns: m.columns.map((c) =>
                      c.name === columnName ? { ...c, description } : c
                    ),
                  }
                : m
            ),
          }
        : s
    );
    setSaved(false);
  };

  // Fills only currently-empty fields with AI-generated text (the backend does the
  // same filtering); anything already typed, including a description you just typed
  // while this was in flight, is left alone. Nothing is saved until you hit Save.
  const generateFor = async (modelName: string) => {
    setGenerating((prev) => new Set(prev).add(modelName));
    setGenerateErrors((prev) => {
      const { [modelName]: _drop, ...rest } = prev;
      return rest;
    });
    try {
      const generated = await api.generateDescriptions(modelName);
      setSemantics((s) =>
        s
          ? {
              ...s,
              models: s.models.map((m) =>
                m.name !== modelName
                  ? m
                  : {
                      ...m,
                      description: m.description || generated.description,
                      columns: m.columns.map((c) => {
                        const match = generated.columns.find((gc) => gc.name === c.name);
                        return c.description || !match ? c : { ...c, description: match.description };
                      }),
                    }
              ),
            }
          : s
      );
      setSaved(false);
    } catch (e) {
      setGenerateErrors((prev) => ({ ...prev, [modelName]: errorMessage(e) }));
    } finally {
      setGenerating((prev) => {
        const next = new Set(prev);
        next.delete(modelName);
        return next;
      });
    }
  };

  const save = async () => {
    if (!semantics) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const result = await api.putSemantics(semantics);
      setSemantics(result);
      setSavedJson(JSON.stringify(result));
      setSaved(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold mb-1">Semantics</h1>
      <p className="text-sm text-gray-600 mb-6">
        Describe each model and column. Names and types come from the warehouse and
        aren&rsquo;t editable here — only descriptions are.
      </p>

      {error && (
        <p className="mb-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}

      <div className="flex items-center gap-3 mb-4">
        <button className={buttonClass} disabled={!semantics || !dirty || saving} onClick={save}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button className={secondaryButtonClass} disabled={loading} onClick={refresh}>
          Refresh
        </button>
        <button className={secondaryButtonClass} disabled={loading} onClick={syncFromTables}>
          Sync from tables
        </button>
        {dirty && <span className="text-xs text-amber-600">Unsaved changes</span>}
        {saved && !dirty && <span className="text-xs text-green-700">Saved.</span>}
      </div>

      {loading && <p className="text-sm text-gray-500">Loading…</p>}

      {!loading && semantics && semantics.models.length === 0 && (
        <p className="text-sm text-gray-500 mb-6">
          No tables described yet — connect or upload a source, then come back here.
        </p>
      )}

      {!loading &&
        semantics &&
        semantics.models.map((model) => (
          <section key={model.name} className="mb-6 rounded border border-gray-200 p-4">
            <div className="flex items-center justify-between mb-1">
              <h2 className="font-semibold">{model.name}</h2>
              <button
                className={linkButtonClass}
                disabled={generating.has(model.name)}
                onClick={() => generateFor(model.name)}
              >
                {generating.has(model.name) ? "Generating…" : "Generate AI description"}
              </button>
            </div>
            {generateErrors[model.name] && (
              <p className="mb-2 text-xs text-red-700">{generateErrors[model.name]}</p>
            )}
            <input
              className={`${inputClass} mb-3`}
              placeholder="What does this table represent?"
              value={model.description}
              onChange={(e) => setModelDescription(model.name, e.target.value)}
            />
            <ul className="divide-y divide-gray-100">
              {model.columns.map((column) => (
                <li key={column.name} className="py-2 flex items-center gap-3">
                  <span className="w-40 shrink-0 text-sm">
                    {column.name} <span className="text-gray-400">— {column.type}</span>
                  </span>
                  <input
                    className={inputClass}
                    placeholder="What does this column mean?"
                    value={column.description}
                    onChange={(e) => setColumnDescription(model.name, column.name, e.target.value)}
                  />
                </li>
              ))}
            </ul>
          </section>
        ))}

      <section className="mt-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Relationships
        </h2>
        <RelationshipsPanel />
      </section>
    </div>
  );
}
