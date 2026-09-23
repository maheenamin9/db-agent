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
};
