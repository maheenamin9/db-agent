"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { api, ApiError, type SourceOut, type TableOut } from "../../lib/api";

const buttonClass =
  "rounded bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50";

function SchemaPreview({ table }: { table: TableOut }) {
  return (
    <details className="mt-1">
      <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
        {table.columns.length} column{table.columns.length === 1 ? "" : "s"}
      </summary>
      <ul className="mt-1 ml-4 text-xs text-gray-600 list-disc">
        {table.columns.map((c) => (
          <li key={c.name}>
            {c.name} <span className="text-gray-400">— {c.type}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function ErrorBox({ message }: { message: string }) {
  return <p className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{message}</p>;
}

function errorMessage(e: unknown) {
  return e instanceof ApiError ? e.message : String(e);
}

/** Live tables of a specific connected database, with an "import selected" action.
 * Only shown when the page is reached with ?source=<id> (e.g. from the Sources page). */
function ImportFromSource({ sourceId, onImported }: { sourceId: string; onImported: () => void }) {
  const [source, setSource] = useState<SourceOut | null>(null);
  const [tables, setTables] = useState<TableOut[] | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [imported, setImported] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    Promise.all([api.listSources(), api.sourceTables(sourceId)])
      .then(([sources, sourceTables]) => {
        setSource(sources.find((s) => s.id === sourceId) ?? null);
        setTables(sourceTables);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [sourceId]);

  const toggle = (name: string) =>
    setChecked((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const submit = async () => {
    setBusy(true);
    setError(null);
    setImported(null);
    try {
      const res = await api.importTables(sourceId, [...checked]);
      setImported(res.imported.map((t) => `${t.name} (${t.rows} rows)`).join(", "));
      setChecked(new Set());
      onImported();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mb-8 rounded border border-gray-200 p-4">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Import from {source ? `${source.name} (${source.type})` : "connected source"}
      </h2>
      {error && <ErrorBox message={error} />}
      {!tables && !error && <p className="text-sm text-gray-500">Loading…</p>}
      {tables && tables.length === 0 && <p className="text-sm text-gray-500">No tables found.</p>}
      {tables && tables.length > 0 && (
        <>
          <ul className="divide-y divide-gray-200 border border-gray-200 rounded mb-3">
            {tables.map((t) => (
              <li key={t.name} className="px-3 py-2 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checked.has(t.name)}
                    onChange={() => toggle(t.name)}
                  />
                  <span className="font-medium">{t.name}</span>
                </label>
                <SchemaPreview table={t} />
              </li>
            ))}
          </ul>
          <button className={buttonClass} disabled={checked.size === 0 || busy} onClick={submit}>
            {busy ? "Importing…" : `Import selected (${checked.size})`}
          </button>
        </>
      )}
      {imported && (
        <p className="mt-3 rounded border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          Imported: {imported}
        </p>
      )}
    </section>
  );
}

/** Every table currently in DuckDB, with the "part of the project" selection. */
function ProjectTables() {
  const [tables, setTables] = useState<TableOut[] | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  const refresh = () => {
    setError(null);
    Promise.all([api.listTables(), api.getSelection()])
      .then(([allTables, selection]) => {
        setTables(allTables);
        const names = allTables.map((t) => t.name);
        // No selection saved yet (tables: null) means "everything" — matches how the
        // warehouse behaved before this feature existed.
        setChecked(new Set(selection.tables ?? names));
      })
      .catch((e) => setError(errorMessage(e)));
  };

  useEffect(refresh, []);

  const toggle = (name: string) =>
    setChecked((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const submit = async () => {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await api.selectTables([...checked]);
      setSaved(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Tables in your project
      </h2>
      <p className="text-xs text-gray-500 mb-2">
        This is what gets described in Semantics and indexed in Deploy — uncheck anything that
        shouldn&rsquo;t be.
      </p>
      {error && <ErrorBox message={error} />}
      {!tables && !error && <p className="text-sm text-gray-500">Loading…</p>}
      {tables && tables.length === 0 && (
        <p className="text-sm text-gray-500">
          No tables yet — connect or upload a source first.
        </p>
      )}
      {tables && tables.length > 0 && (
        <>
          <ul className="divide-y divide-gray-200 border border-gray-200 rounded mb-3">
            {tables.map((t) => (
              <li key={t.name} className="px-3 py-2 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checked.has(t.name)}
                    onChange={() => toggle(t.name)}
                  />
                  <span className="font-medium">{t.name}</span>
                </label>
                <SchemaPreview table={t} />
              </li>
            ))}
          </ul>
          <button className={buttonClass} disabled={checked.size === 0 || busy} onClick={submit}>
            {busy ? "Saving…" : "Save selection"}
          </button>
          {saved && <span className="ml-3 text-sm text-green-700">Saved.</span>}
        </>
      )}
    </section>
  );
}

function TablesPageInner() {
  const sourceId = useSearchParams().get("source");
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold mb-1">Tables</h1>
      <p className="text-sm text-gray-600 mb-6">Pick which tables become part of the project.</p>

      {sourceId && (
        <ImportFromSource sourceId={sourceId} onImported={() => setRefreshKey((k) => k + 1)} />
      )}
      <ProjectTables key={refreshKey} />
    </div>
  );
}

export default function TablesPage() {
  return (
    <Suspense fallback={<p className="text-sm text-gray-500">Loading…</p>}>
      <TablesPageInner />
    </Suspense>
  );
}
