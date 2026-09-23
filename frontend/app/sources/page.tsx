"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError, type SourceOut, type TableOut } from "../../lib/api";

type SourceKind = "file" | "postgres" | "mysql" | "gsheets";

const KIND_LABELS: Record<SourceKind, string> = {
  file: "File (CSV/Excel)",
  postgres: "Postgres",
  mysql: "MySQL",
  gsheets: "Google Sheets",
};

const DEFAULT_PORT: Record<"postgres" | "mysql", string> = { postgres: "5432", mysql: "3306" };

const inputClass =
  "w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none";
const labelClass = "block text-sm font-medium text-gray-700 mb-1";
const buttonClass =
  "rounded bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50";

export default function SourcesPage() {
  const [sources, setSources] = useState<SourceOut[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [kind, setKind] = useState<SourceKind>("file");

  const refreshSources = () => {
    setLoadingSources(true);
    api
      .listSources()
      .then(setSources)
      .catch((e) => setListError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setLoadingSources(false));
  };

  useEffect(refreshSources, []);

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold mb-1">Sources</h1>
      <p className="text-sm text-gray-600 mb-6">
        Connect CSV/Excel files, Google Sheets, Postgres or MySQL. Databases are browsed live; files and
        sheets are loaded in immediately.
      </p>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Connected databases
        </h2>
        {loadingSources && <p className="text-sm text-gray-500">Loading…</p>}
        {listError && <p className="text-sm text-red-600">{listError}</p>}
        {!loadingSources && !listError && sources.length === 0 && (
          <p className="text-sm text-gray-500">No databases connected yet.</p>
        )}
        <ul className="divide-y divide-gray-200 border border-gray-200 rounded">
          {sources.map((s) => (
            <li key={s.id} className="flex items-center justify-between px-3 py-2 text-sm">
              <span>
                <span className="font-medium">{s.name}</span>{" "}
                <span className="text-gray-500">({s.type})</span>
              </span>
              <Link className="text-blue-600 hover:underline" href={`/tables?source=${s.id}`}>
                Browse tables →
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Add a source</h2>
        <div className="flex gap-2 mb-4">
          {(Object.keys(KIND_LABELS) as SourceKind[]).map((k) => (
            <button
              key={k}
              onClick={() => setKind(k)}
              className={`rounded px-3 py-1 text-sm border ${
                kind === k ? "bg-gray-900 text-white border-gray-900" : "border-gray-300 text-gray-700"
              }`}
            >
              {KIND_LABELS[k]}
            </button>
          ))}
        </div>

        {kind === "file" && <FileForm />}
        {(kind === "postgres" || kind === "mysql") && (
          <DatabaseForm dbType={kind} onConnected={refreshSources} />
        )}
        {kind === "gsheets" && <GSheetsForm />}
      </section>
    </div>
  );
}

function ResultSummary({ tables }: { tables: TableOut[] }) {
  return (
    <div className="mt-3 rounded border border-green-200 bg-green-50 p-3 text-sm text-green-800">
      Loaded {tables.length === 1 ? "1 table" : `${tables.length} tables`}:{" "}
      {tables.map((t) => t.name).join(", ")}.{" "}
      <Link href="/tables" className="underline">
        Go to Tables →
      </Link>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return <p className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{message}</p>;
}

function FileForm() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TableOut[] | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.uploadFile(file);
      setResult(res.tables);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <div>
        <label className={labelClass}>CSV or Excel file</label>
        <input
          type="file"
          accept=".csv,.xlsx"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm"
        />
        {file && <p className="mt-1 text-xs text-gray-500">Selected: {file.name}</p>}
      </div>
      <button className={buttonClass} disabled={!file || busy} onClick={submit}>
        {busy ? "Uploading…" : "Upload"}
      </button>
      {!file && <p className="text-xs text-gray-400">Choose a file above to enable Upload.</p>}
      {error && <ErrorBox message={error} />}
      {result && <ResultSummary tables={result} />}
    </div>
  );
}

function DatabaseForm({
  dbType,
  onConnected,
}: {
  dbType: "postgres" | "mysql";
  onConnected: () => void;
}) {
  const [form, setForm] = useState({
    name: "",
    host: "",
    port: DEFAULT_PORT[dbType],
    database: "",
    user: "",
    password: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState<SourceOut | null>(null);

  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const submit = async () => {
    setBusy(true);
    setError(null);
    setConnected(null);
    try {
      const source = await api.createSource({
        type: dbType,
        name: form.name || undefined,
        config: {
          host: form.host,
          port: Number(form.port),
          database: form.database,
          user: form.user,
          password: form.password,
        },
      });
      setConnected(source);
      onConnected();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500">
        Use read-only credentials — the agent should never connect with an admin account.
      </p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Name (optional)</label>
          <input className={inputClass} value={form.name} onChange={set("name")} placeholder={dbType} />
        </div>
        <div>
          <label className={labelClass}>Host</label>
          <input className={inputClass} value={form.host} onChange={set("host")} placeholder="localhost" />
        </div>
        <div>
          <label className={labelClass}>Port</label>
          <input className={inputClass} value={form.port} onChange={set("port")} />
        </div>
        <div>
          <label className={labelClass}>Database</label>
          <input className={inputClass} value={form.database} onChange={set("database")} />
        </div>
        <div>
          <label className={labelClass}>User</label>
          <input className={inputClass} value={form.user} onChange={set("user")} placeholder="readonly" />
        </div>
        <div>
          <label className={labelClass}>Password</label>
          <input
            type="password"
            className={inputClass}
            value={form.password}
            onChange={set("password")}
          />
        </div>
      </div>
      <button
        className={buttonClass}
        disabled={busy || !form.host || !form.database || !form.user}
        onClick={submit}
      >
        {busy ? "Connecting…" : "Connect"}
      </button>
      {error && <ErrorBox message={error} />}
      {connected && (
        <div className="mt-3 rounded border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          Connected as &ldquo;{connected.name}&rdquo;.{" "}
          <Link href={`/tables?source=${connected.id}`} className="underline">
            Browse its tables →
          </Link>
        </div>
      )}
    </div>
  );
}

function GSheetsForm() {
  const [spreadsheet, setSpreadsheet] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TableOut[] | null>(null);

  const submit = async () => {
    if (!spreadsheet) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.importGsheets(spreadsheet, name || undefined);
      setResult(res.tables);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500">
        Share the spreadsheet with the service account&rsquo;s email as a Viewer first.
      </p>
      <div>
        <label className={labelClass}>Spreadsheet URL or id</label>
        <input
          className={inputClass}
          value={spreadsheet}
          onChange={(e) => setSpreadsheet(e.target.value)}
          placeholder="https://docs.google.com/spreadsheets/d/..."
        />
      </div>
      <div>
        <label className={labelClass}>Name (optional)</label>
        <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <button className={buttonClass} disabled={!spreadsheet || busy} onClick={submit}>
        {busy ? "Loading…" : "Load"}
      </button>
      {error && <ErrorBox message={error} />}
      {result && <ResultSummary tables={result} />}
    </div>
  );
}
