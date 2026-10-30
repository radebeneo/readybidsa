// Server-side helpers for calling the ReadyBid API.
// Only import this from Server Components or route handlers.

export type HealthResponse = {
  status: "ok";
  service: string;
  version: string;
};

export type IntegrationState = {
  configured: boolean;
  /** null means the API did not check reachability. */
  reachable: boolean | null;
  detail: string | null;
};

export type IntegrationsResponse = {
  supabase: IntegrationState;
  groq: IntegrationState & { model: string };
  redis: IntegrationState;
};

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; reason: "not-configured" | "unreachable" | "bad-response"; message: string };

/**
 * Base URL of the FastAPI service.
 * `API_URL` is read at request time on the server; `NEXT_PUBLIC_API_URL` is
 * inlined at build time and used as a fallback.
 * Call after `await io()` (or another suspension point) when Cache Components is on.
 */
export function getApiBaseUrl(): string | null {
  const value = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL;
  if (!value || value.trim() === "") return null;
  return value.trim().replace(/\/+$/, "");
}

export async function apiGet<T>(path: string, timeoutMs = 3000): Promise<ApiResult<T>> {
  const base = getApiBaseUrl();
  if (!base) {
    return {
      ok: false,
      reason: "not-configured",
      message: "Integration not configured: set API_URL or NEXT_PUBLIC_API_URL.",
    };
  }

  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { ok: false, reason: "unreachable", message: `Could not reach ${base}: ${message}` };
  }

  if (!response.ok) {
    return { ok: false, reason: "bad-response", message: `${path} returned HTTP ${response.status}` };
  }

  try {
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, reason: "bad-response", message: `${path} did not return valid JSON` };
  }
}
