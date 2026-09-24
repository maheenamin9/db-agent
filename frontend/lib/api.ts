// Talks to the FastAPI backend. This file runs in the browser (every page that
// uses it is a Client Component), so it always uses NEXT_PUBLIC_API_URL, never
// the Docker-internal API_INTERNAL_URL that app/health/page.tsx uses server-side.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ColumnInfo = { name: string; type: string; nullable: boolean };
export type TableOut = { name: string; columns: ColumnInfo[] };
export type SourceOut = { id: string; type: "postgres" | "mysql"; name: string };
export type ImportResponse = { imported: { name: string; rows: number }[] };
export type UploadResponse = { tables: TableOut[] };
export type Selection = { tables: string[] | null };

export type Cardinality = "one_to_one" | "one_to_many" | "many_to_one" | "many_to_many";

export type Column = { name: string; type: string | null; description: string };
export type Model = { name: string; description: string; columns: Column[] };
export type Relationship = {
  id: string;
  from_model: string;
  from_column: string;
  to_model: string;
  to_column: string;
  cardinality: Cardinality;
};
export type Suggestion = Omit<Relationship, "id"> & { confidence: number; reason: string };
export type Semantics = { models: Model[]; relationships: Relationship[] };
export type RelationshipInput = Omit<Relationship, "id">;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail =
      typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? res.statusText);
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  listSources: () => request<SourceOut[]>("/sources"),

  createSource: (body: { type: "postgres" | "mysql"; name?: string; config: Record<string, unknown> }) =>
    request<SourceOut>("/sources", { method: "POST", body: JSON.stringify(body) }),

  sourceTables: (sourceId: string) => request<TableOut[]>(`/sources/${sourceId}/tables`),

  importTables: (sourceId: string, tables: string[]) =>
    request<ImportResponse>(`/sources/${sourceId}/import`, {
      method: "POST",
      body: JSON.stringify({ tables }),
    }),

  uploadFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResponse>("/sources/upload", { method: "POST", body: form });
  },

  importGsheets: (spreadsheetIdOrUrl: string, name?: string) =>
    request<UploadResponse>("/sources/gsheets", {
      method: "POST",
      body: JSON.stringify({ spreadsheet_id: spreadsheetIdOrUrl, name: name || undefined }),
    }),

  listTables: () => request<TableOut[]>("/tables"),

  getSelection: () => request<Selection>("/tables/selection"),

  selectTables: (tables: string[]) =>
    request<Selection>("/tables/select", { method: "POST", body: JSON.stringify({ tables }) }),

  deleteTable: (name: string) =>
    request<{ table: string; model_removed: boolean; relationships_removed: number }>(
      `/tables/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    ),

  getSemantics: () => request<Semantics>("/semantics"),

  putSemantics: (semantics: Semantics) =>
    request<Semantics>("/semantics", { method: "PUT", body: JSON.stringify(semantics) }),

  syncSemantics: () => request<Semantics>("/semantics/sync", { method: "POST" }),

  listRelationships: () => request<Relationship[]>("/relationships"),

  suggestRelationships: (tables?: string[]) =>
    request<Suggestion[]>("/relationships/suggest", {
      method: "POST",
      body: JSON.stringify(tables ? { tables } : {}),
    }),

  createRelationship: (body: RelationshipInput) =>
    request<Relationship>("/relationships", { method: "POST", body: JSON.stringify(body) }),

  updateRelationship: (id: string, body: RelationshipInput) =>
    request<Relationship>(`/relationships/${id}`, { method: "PUT", body: JSON.stringify(body) }),

  deleteRelationship: (id: string) =>
    request<void>(`/relationships/${id}`, { method: "DELETE" }),
};
