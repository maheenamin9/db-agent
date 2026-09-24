"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError, type DeployResponse, type Semantics } from "../../lib/api";

const buttonClass =
  "rounded bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50";

function errorMessage(e: unknown) {
  return e instanceof ApiError ? e.message : String(e);
}

function describedCount<T extends { description: string }>(items: T[]) {
  return items.filter((i) => i.description.trim()).length;
}

export default function DeployPage() {
  const [semantics, setSemantics] = useState<Semantics | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deploying, setDeploying] = useState(false);
  const [deployError, setDeployError] = useState<string | null>(null);
  const [result, setResult] = useState<DeployResponse | null>(null);

  useEffect(() => {
    api.getSemantics().then(setSemantics).catch((e) => setLoadError(errorMessage(e)));
  }, []);

  const columns = semantics ? semantics.models.flatMap((m) => m.columns) : [];
  const modelCount = semantics?.models.length ?? 0;

  const deploy = async () => {
    setDeploying(true);
    setDeployError(null);
    setResult(null);
    try {
      setResult(await api.deploy());
    } catch (e) {
      setDeployError(errorMessage(e));
    } finally {
      setDeploying(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold mb-1">Deploy</h1>
      <p className="text-sm text-gray-600 mb-6">
        Embed the current semantics and upsert them into Qdrant. This wipes and rebuilds the whole
        collection each time — it&rsquo;s a full re-index, not an incremental update.
      </p>

      {loadError && (
        <p className="mb-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {loadError}
        </p>
      )}

      {semantics && (
        <div className="mb-4 rounded border border-gray-200 p-4 text-sm">
          <p className="font-semibold text-gray-500 uppercase tracking-wide text-xs mb-2">
            Ready to deploy
          </p>
          {modelCount === 0 ? (
            <p className="text-gray-500">
              Nothing described yet — go to{" "}
              <Link href="/semantics" className="text-blue-600 hover:underline">
                Semantics
              </Link>{" "}
              first.
            </p>
          ) : (
            <ul className="space-y-1 text-gray-700">
              <li>
                {modelCount} table{modelCount === 1 ? "" : "s"} ({describedCount(semantics.models)} with a
                description)
              </li>
              <li>
                {columns.length} column{columns.length === 1 ? "" : "s"} ({describedCount(columns)} with a
                description)
              </li>
              <li>
                {semantics.relationships.length} relationship
                {semantics.relationships.length === 1 ? "" : "s"}
              </li>
            </ul>
          )}
        </div>
      )}

      <button className={buttonClass} disabled={!semantics || modelCount === 0 || deploying} onClick={deploy}>
        {deploying ? "Deploying…" : "Deploy"}
      </button>

      {deployError && (
        <p className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {deployError}
        </p>
      )}

      {result && (
        <div className="mt-4 rounded border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          Deployed {result.points} point{result.points === 1 ? "" : "s"} to collection &ldquo;
          {result.collection}&rdquo;: {result.models} model{result.models === 1 ? "" : "s"},{" "}
          {result.columns} column{result.columns === 1 ? "" : "s"}, {result.relationships} relationship
          {result.relationships === 1 ? "" : "s"}.{" "}
          <Link href="/ask" className="underline">
            Go to Ask →
          </Link>
        </div>
      )}
    </div>
  );
}
