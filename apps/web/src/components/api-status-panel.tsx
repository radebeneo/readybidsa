import { io } from "next/cache";
import {
  apiGet,
  getApiBaseUrl,
  type HealthResponse,
  type IntegrationState,
  type IntegrationsResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Tone = "ok" | "warn" | "error";

function StatusPill({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        tone === "ok" && "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
        tone === "warn" && "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
        tone === "error" && "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "size-1.5 rounded-full",
          tone === "ok" && "bg-emerald-500",
          tone === "warn" && "bg-amber-500",
          tone === "error" && "bg-red-500",
        )}
      />
      {children}
    </span>
  );
}

function Row({ label, tone, status, detail }: { label: string; tone: Tone; status: string; detail?: string | null }) {
  return (
    <li className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-medium">{label}</p>
        {detail ? <p className="text-xs text-muted-foreground">{detail}</p> : null}
      </div>
      <StatusPill tone={tone}>{status}</StatusPill>
    </li>
  );
}

function integrationRow(label: string, state: IntegrationState) {
  if (!state.configured) {
    return <Row key={label} label={label} tone="warn" status="Integration not configured" detail={state.detail} />;
  }
  if (state.reachable === false) {
    return <Row key={label} label={label} tone="error" status="Not reachable" detail={state.detail} />;
  }
  return <Row key={label} label={label} tone="ok" status="Configured" detail={state.detail} />;
}

/** Live API status. Render inside <Suspense>; it is request-time data. */
export async function ApiStatusPanel() {
  await io();
  const baseUrl = getApiBaseUrl();

  const [health, integrations] = await Promise.all([
    apiGet<HealthResponse>("/health"),
    apiGet<IntegrationsResponse>("/integrations/status"),
  ]);

  return (
    <ul className="divide-y divide-border">
      <Row
        label="API service"
        tone={health.ok ? "ok" : health.reason === "not-configured" ? "warn" : "error"}
        status={
          health.ok
            ? `Online (v${health.data.version})`
            : health.reason === "not-configured"
              ? "Integration not configured"
              : "Unreachable"
        }
        detail={health.ok ? baseUrl : health.message}
      />
      {integrations.ok ? (
        <>
          {integrationRow("Supabase (database, auth, storage)", integrations.data.supabase)}
          {integrationRow(`Groq (${integrations.data.groq.model})`, integrations.data.groq)}
          {integrationRow("Redis job queue", integrations.data.redis)}
        </>
      ) : (
        <Row
          label="Integrations"
          tone="warn"
          status="Status unavailable"
          detail="Integration status is reported by the API. Start the API to see it."
        />
      )}
    </ul>
  );
}

export function ApiStatusPanelSkeleton() {
  return (
    <ul className="divide-y divide-border" aria-busy="true" aria-label="Loading service status">
      {["API service", "Supabase", "Groq", "Redis"].map((label) => (
        <li key={label} className="flex items-center justify-between py-3">
          <p className="text-sm font-medium">{label}</p>
          <span className="h-5 w-28 animate-pulse rounded-full bg-muted" />
        </li>
      ))}
    </ul>
  );
}
