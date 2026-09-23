"use client";

import { useEffect, useState } from "react";

import {
  api,
  ApiError,
  type Cardinality,
  type Relationship,
  type RelationshipInput,
  type Suggestion,
  type TableOut,
} from "../lib/api";

const CARDINALITIES: Cardinality[] = ["many_to_one", "one_to_many", "one_to_one", "many_to_many"];

const buttonClass =
  "rounded bg-gray-900 px-3 py-1 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50";
const linkButtonClass = "text-sm text-blue-600 hover:underline";
const selectClass = "rounded border border-gray-300 px-2 py-1 text-sm";

function errorMessage(e: unknown) {
  return e instanceof ApiError ? e.message : String(e);
}

const emptyForm: RelationshipInput = {
  from_model: "",
  from_column: "",
  to_model: "",
  to_column: "",
  cardinality: "many_to_one",
};

/** Lists saved relationships with add/edit/delete, plus a heuristic "Suggest" step
 * from Task 6. Reused as-is on both /relationships and /semantics (Task 9 asks for
 * this exact view embedded in the semantics editor). */
export default function RelationshipsPanel() {
  const [tables, setTables] = useState<TableOut[]>([]);
  const [relationships, setRelationships] = useState<Relationship[] | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // null = form hidden, "new" = adding, an id = editing that relationship
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<RelationshipInput>(emptyForm);

  const refresh = () => {
    setError(null);
    Promise.all([api.listTables(), api.listRelationships()])
      .then(([t, r]) => {
        setTables(t);
        setRelationships(r);
      })
      .catch((e) => setError(errorMessage(e)));
  };

  useEffect(refresh, []);

  const columnsFor = (modelName: string) => tables.find((t) => t.name === modelName)?.columns ?? [];

  const startAdd = (prefill?: RelationshipInput) => {
    setForm(prefill ?? emptyForm);
    setEditing("new");
  };

  const startEdit = (rel: Relationship) => {
    setForm({
      from_model: rel.from_model,
      from_column: rel.from_column,
      to_model: rel.to_model,
      to_column: rel.to_column,
      cardinality: rel.cardinality,
    });
    setEditing(rel.id);
  };

  const cancelForm = () => {
    setEditing(null);
    setForm(emptyForm);
  };

  const submitForm = async () => {
    setBusy(true);
    setError(null);
    try {
      if (editing === "new") {
        await api.createRelationship(form);
      } else if (editing) {
        await api.updateRelationship(editing, form);
      }
      cancelForm();
      refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this relationship?")) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteRelationship(id);
      refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const runSuggest = async () => {
    setBusy(true);
    setError(null);
    try {
      setSuggestions(await api.suggestRelationships());
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const acceptSuggestion = async (s: Suggestion) => {
    setBusy(true);
    setError(null);
    try {
      const { confidence: _confidence, reason: _reason, ...body } = s;
      await api.createRelationship(body);
      setSuggestions((prev) => (prev ?? []).filter((x) => x !== s));
      refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const formValid =
    form.from_model && form.from_column && form.to_model && form.to_column;

  return (
    <div>
      {error && (
        <p className="mb-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}

      {relationships === null && <p className="text-sm text-gray-500">Loading…</p>}

      {relationships !== null && (
        <>
          {relationships.length === 0 && (
            <p className="text-sm text-gray-500 mb-3">No relationships saved yet.</p>
          )}
          <ul className="divide-y divide-gray-200 border border-gray-200 rounded mb-3">
            {relationships.map((r) => (
              <li key={r.id} className="flex items-center justify-between px-3 py-2 text-sm">
                <span>
                  <span className="font-medium">
                    {r.from_model}.{r.from_column}
                  </span>{" "}
                  → <span className="font-medium">{r.to_model}.{r.to_column}</span>{" "}
                  <span className="text-gray-400">({r.cardinality})</span>
                </span>
                <span className="flex gap-3">
                  <button className={linkButtonClass} onClick={() => startEdit(r)}>
                    Edit
                  </button>
                  <button className="text-sm text-red-600 hover:underline" onClick={() => remove(r.id)}>
                    Delete
                  </button>
                </span>
              </li>
            ))}
          </ul>

          <div className="flex gap-4 mb-3">
            <button className={linkButtonClass} onClick={() => startAdd()} disabled={editing !== null}>
              + Add relationship
            </button>
            <button className={linkButtonClass} onClick={runSuggest} disabled={busy}>
              Suggest relationships
            </button>
          </div>
        </>
      )}

      {suggestions !== null && (
        <div className="mb-4 rounded border border-blue-200 bg-blue-50 p-3">
          <p className="text-xs font-semibold text-blue-900 uppercase tracking-wide mb-2">
            Suggestions
          </p>
          {suggestions.length === 0 && (
            <p className="text-sm text-blue-800">No new suggestions.</p>
          )}
          <ul className="space-y-2">
            {suggestions.map((s, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span>
                  <span className="font-medium">
                    {s.from_model}.{s.from_column}
                  </span>{" "}
                  → <span className="font-medium">{s.to_model}.{s.to_column}</span>{" "}
                  <span className="text-gray-500">
                    ({Math.round(s.confidence * 100)}% — {s.reason})
                  </span>
                </span>
                <button className={linkButtonClass} onClick={() => acceptSuggestion(s)} disabled={busy}>
                  Add
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {editing !== null && (
        <div className="rounded border border-gray-300 p-3 space-y-2">
          <p className="text-sm font-medium">{editing === "new" ? "New relationship" : "Edit relationship"}</p>
          <div className="grid grid-cols-2 gap-2 items-center text-sm">
            <select
              className={selectClass}
              value={form.from_model}
              onChange={(e) => setForm((f) => ({ ...f, from_model: e.target.value, from_column: "" }))}
            >
              <option value="">from table…</option>
              {tables.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name}
                </option>
              ))}
            </select>
            <select
              className={selectClass}
              value={form.from_column}
              onChange={(e) => setForm((f) => ({ ...f, from_column: e.target.value }))}
              disabled={!form.from_model}
            >
              <option value="">column…</option>
              {columnsFor(form.from_model).map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
            <select
              className={selectClass}
              value={form.to_model}
              onChange={(e) => setForm((f) => ({ ...f, to_model: e.target.value, to_column: "" }))}
            >
              <option value="">to table…</option>
              {tables.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name}
                </option>
              ))}
            </select>
            <select
              className={selectClass}
              value={form.to_column}
              onChange={(e) => setForm((f) => ({ ...f, to_column: e.target.value }))}
              disabled={!form.to_model}
            >
              <option value="">column…</option>
              {columnsFor(form.to_model).map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <select
            className={selectClass}
            value={form.cardinality}
            onChange={(e) => setForm((f) => ({ ...f, cardinality: e.target.value as Cardinality }))}
          >
            {CARDINALITIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <div className="flex gap-3 pt-1">
            <button className={buttonClass} disabled={!formValid || busy} onClick={submitForm}>
              {editing === "new" ? "Add" : "Save"}
            </button>
            <button className="text-sm text-gray-500 hover:underline" onClick={cancelForm}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
