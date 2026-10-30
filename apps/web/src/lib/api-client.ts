// Browser-side client for the ReadyBid API.
// Every call sends the signed-in user's Supabase access token as a bearer token. The API
// verifies it and checks organisation membership; nothing here is trusted on its own.
import type {
  AnalysisOut,
  ChecklistOut,
  DecisionIn,
  DecisionOut,
  DocumentOut,
  EvidenceDocumentOut,
  EvidenceLabel,
  EvidenceListOut,
  EvidenceSourceViewOut,
  FileUrlOut,
  JobOut,
  OrganisationOut,
  RequirementsOut,
  SourceViewOut,
  TenderDetailOut,
  TenderOut,
} from "@/lib/api-types";
import { SUPABASE_NOT_CONFIGURED, getSupabase } from "@/lib/supabase-browser";

// Inlined at build time. The browser calls the API directly, so the web origin must be
// listed in the API's CORS_ORIGINS.
const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").trim().replace(/\/+$/, "");

export const API_NOT_CONFIGURED =
  "Set NEXT_PUBLIC_API_URL in apps/web/.env.local to the ReadyBid API address, then restart or rebuild the web app.";

export function isApiConfigured(): boolean {
  return API_BASE !== "";
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** A value fetched from the API: still loading, failed with a message, or ready. */
export type Loadable<T> =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; data: T };

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (isAbortError(error)) return "The request was cancelled.";
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong. Try again.";
}

/** Returns the URL only if it is http(s), so API data can never inject a javascript: link. */
export function safeHttpUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function fallbackMessage(status: number): string {
  switch (status) {
    case 401:
      return "Your session has expired. Sign in again.";
    case 403:
      return "You do not have access to this.";
    case 404:
      return "Not found.";
    case 409:
      return "This conflicts with a change made at the same time. Try again.";
    case 413:
      return "The file is too large.";
    case 502:
    case 503:
      return "A service is unavailable right now. Try again shortly.";
    default:
      return `The request failed (HTTP ${status}).`;
  }
}

// FastAPI errors use `detail` as a string, an upload error object `{code, message}` or a
// list of validation errors.
function describeError(status: number, body: unknown): { message: string; code: string | null } {
  const detail = isRecord(body) ? body.detail : undefined;
  if (typeof detail === "string" && detail.trim() !== "") return { message: detail, code: null };
  if (isRecord(detail) && typeof detail.message === "string") {
    return { message: detail.message, code: typeof detail.code === "string" ? detail.code : null };
  }
  if (Array.isArray(detail)) {
    const first = detail.find(isRecord);
    if (first && typeof first.msg === "string") return { message: first.msg, code: "validation" };
  }
  return { message: fallbackMessage(status), code: null };
}

function requireApiBase(): string {
  if (!API_BASE) throw new ApiError(`Integration not configured. ${API_NOT_CONFIGURED}`, 0, "not_configured");
  return API_BASE;
}

async function accessToken(): Promise<string> {
  const supabase = getSupabase();
  if (!supabase) {
    throw new ApiError(`Integration not configured. ${SUPABASE_NOT_CONFIGURED}`, 0, "not_configured");
  }
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new ApiError("Sign in to continue.", 401, "signed_out");
  return token;
}

function unreachable(base: string): ApiError {
  return new ApiError(`Could not reach the ReadyBid API at ${base}.`, 0, "unreachable");
}

type RequestOptions = {
  method?: "GET" | "POST";
  json?: unknown;
  signal?: AbortSignal;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const base = requireApiBase();
  const token = await accessToken();
  const headers: Record<string, string> = {
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
  };
  let body: string | undefined;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }

  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
      signal: options.signal,
      cache: "no-store",
    });
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw unreachable(base);
  }

  let parsed: unknown = null;
  try {
    parsed = await response.json();
  } catch {
    parsed = null;
  }

  if (!response.ok) {
    const { message, code } = describeError(response.status, parsed);
    throw new ApiError(message, response.status, code);
  }
  if (parsed === null) {
    throw new ApiError("The API returned an unexpected response.", response.status, "bad_response");
  }
  return parsed as T;
}

const segment = encodeURIComponent;

export const api = {
  listOrganisations: () => request<OrganisationOut[]>("/organisations"),

  createOrganisation: (name: string) =>
    request<OrganisationOut>("/organisations", { method: "POST", json: { name } }),

  listTenders: (organisationId: string) =>
    request<TenderOut[]>(`/organisations/${segment(organisationId)}/tenders`),

  createTender: (organisationId: string, input: { title: string; reference: string | null }) =>
    request<TenderOut>(`/organisations/${segment(organisationId)}/tenders`, {
      method: "POST",
      json: input,
    }),

  getTender: (tenderId: string) => request<TenderDetailOut>(`/tenders/${segment(tenderId)}`),

  getDocumentFile: (documentId: string) =>
    request<FileUrlOut>(`/documents/${segment(documentId)}/file`),

  /** `evidenceDocumentIds` is the user's explicit choice. An empty list means no matching. */
  startAnalysis: (tenderId: string, documentId: string, evidenceDocumentIds: string[] = []) =>
    request<AnalysisOut>(`/tenders/${segment(tenderId)}/analyses`, {
      method: "POST",
      json: { document_id: documentId, evidence_document_ids: evidenceDocumentIds },
    }),

  listEvidence: (organisationId: string) =>
    request<EvidenceListOut>(`/organisations/${segment(organisationId)}/evidence`),

  getChecklist: (runId: string) => request<ChecklistOut>(`/analyses/${segment(runId)}/checklist`),

  recordDecision: (runId: string, input: DecisionIn) =>
    request<DecisionOut>(`/analyses/${segment(runId)}/decisions`, { method: "POST", json: input }),

  getEvidenceSource: (sourceId: string) =>
    request<EvidenceSourceViewOut>(`/evidence-sources/${segment(sourceId)}`),

  getJob: (jobId: string, signal?: AbortSignal) =>
    request<JobOut>(`/jobs/${segment(jobId)}`, { signal }),

  getRequirements: (runId: string) =>
    request<RequirementsOut>(`/analyses/${segment(runId)}/requirements`),

  getSource: (sourceId: string) => request<SourceViewOut>(`/sources/${segment(sourceId)}`),
};

/**
 * Upload a tender PDF with progress reporting. `onProgress` receives the fraction of bytes
 * sent (0 to 1).
 */
export function uploadDocument(
  tenderId: string,
  file: File,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<DocumentOut> {
  const form = new FormData();
  form.append("file", file, file.name);
  return uploadForm<DocumentOut>(`/tenders/${segment(tenderId)}/documents`, form, onProgress, signal);
}

/**
 * Upload a supporting PDF to the organisation's evidence library. `label` is the user's own
 * description of the file; the API stores it as a label, never as a verified fact.
 */
export function uploadEvidence(
  organisationId: string,
  file: File,
  label: EvidenceLabel,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<EvidenceDocumentOut> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("label", label);
  return uploadForm<EvidenceDocumentOut>(
    `/organisations/${segment(organisationId)}/evidence`,
    form,
    onProgress,
    signal,
  );
}

export type ExportFormat = "csv" | "json";

/** Download the checklist export. Returns the file contents and a safe file name. */
export async function downloadChecklistExport(
  runId: string,
  format: ExportFormat,
): Promise<{ blob: Blob; filename: string }> {
  const base = requireApiBase();
  const token = await accessToken();
  let response: Response;
  try {
    response = await fetch(`${base}/analyses/${segment(runId)}/export?format=${format}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw unreachable(base);
  }
  if (!response.ok) {
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      parsed = null;
    }
    const { message, code } = describeError(response.status, parsed);
    throw new ApiError(message, response.status, code);
  }
  // The name is built here from the run id, never taken from a response header.
  const safeId = runId.replace(/[^A-Za-z0-9-]/g, "");
  return { blob: await response.blob(), filename: `readybid-checklist-${safeId}.${format}` };
}

/**
 * POST multipart form data with upload progress. Uses XMLHttpRequest because fetch cannot
 * report upload progress.
 */
async function uploadForm<T>(
  path: string,
  form: FormData,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  const base = requireApiBase();
  const token = await accessToken();

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${base}${path}`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.setRequestHeader("Accept", "application/json");

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total);
    });

    xhr.addEventListener("load", () => {
      let parsed: unknown = null;
      try {
        parsed = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        parsed = null;
      }
      const ok = xhr.status >= 200 && xhr.status < 300;
      if (ok && parsed !== null) {
        resolve(parsed as T);
      } else if (ok) {
        reject(new ApiError("The API returned an unexpected response.", xhr.status, "bad_response"));
      } else {
        const { message, code } = describeError(xhr.status, parsed);
        reject(new ApiError(message, xhr.status, code));
      }
    });
    xhr.addEventListener("error", () => reject(unreachable(base)));
    xhr.addEventListener("abort", () => reject(new DOMException("Upload cancelled.", "AbortError")));

    if (signal) {
      if (signal.aborted) {
        reject(new DOMException("Upload cancelled.", "AbortError"));
        return;
      }
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    // The browser sets the multipart Content-Type and Content-Length, which the API requires.
    xhr.send(form);
  });
}
