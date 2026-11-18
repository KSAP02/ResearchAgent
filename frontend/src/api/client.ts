// Typed client for the backend. All paths are relative (/api/...): served via the
// Vite dev proxy locally and the nginx proxy in Docker.

export type FieldValue = string | number | boolean;
export type FieldType = "enum" | "bool" | "int" | "float" | "str";

export interface FormField {
  key: string;
  label: string;
  type: FieldType;
  options: (string | number)[] | null;
  min: number | null;
  max: number | null;
  step: number | null;
  description: string;
  default: FieldValue;
  value: FieldValue;
  requires_restart: boolean;
  danger: string | null;
  phase: number | null;
}

export interface FormSection {
  key: string;
  title: string;
  description: string;
  fields: FormField[];
}

export interface AdminConfig {
  path: string;
  mtime: string | null;
  load_error: string | null;
  sections: FormSection[];
}

export type SettingsValues = Record<string, Record<string, FieldValue>>;

export interface UserSettingsState {
  values: SettingsValues;
  sections: FormSection[];
}

export type Changes = Record<string, Record<string, FieldValue>>;

export interface ResearchResponse {
  run_id: number;
  question: string;
  queries: string[];
  papers: { title: string; url: string }[];
  analysis: string;
  evidence_sufficient: boolean;
  retry_count: number;
  report: string;
}

export class ApiError extends Error {
  status: number;
  fieldErrors: Record<string, string>;

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    const detail = (body as { detail?: unknown } | null)?.detail;
    const fieldErrors =
      detail && typeof detail === "object" && "errors" in detail
        ? ((detail as { errors: Record<string, string> }).errors ?? {})
        : {};
    const message = typeof detail === "string" ? detail : `Request failed (${res.status})`;
    throw new ApiError(res.status, message, fieldErrors);
  }
  return res.json() as Promise<T>;
}

export const api = {
  runResearch: (question: string) =>
    request<ResearchResponse>("/api/research", { method: "POST", body: JSON.stringify({ question }) }),

  getAdminConfig: () => request<AdminConfig>("/api/admin/config"),
  updateAdminConfig: (changes: Changes) =>
    request<AdminConfig>("/api/admin/config", { method: "PUT", body: JSON.stringify({ changes }) }),

  getUserSettings: () => request<UserSettingsState>("/api/user/settings"),
  updateUserSettings: (changes: Changes) =>
    request<UserSettingsState>("/api/user/settings", { method: "PUT", body: JSON.stringify({ changes }) }),
};
