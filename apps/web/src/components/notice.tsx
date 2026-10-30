import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Tone = "info" | "success" | "warn" | "error";

const toneClasses: Record<Tone, string> = {
  info: "border-border bg-muted/50 text-foreground",
  success:
    "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  warn: "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200",
  error: "border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-200",
};

export function Notice({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : undefined}
      className={cn("rounded-lg border px-4 py-3 text-sm", toneClasses[tone], className)}
    >
      {title ? <p className="font-medium">{title}</p> : null}
      {children ? <div className={title ? "mt-1" : undefined}>{children}</div> : null}
    </div>
  );
}

/** An error message with an optional retry button. Use from client components only. */
export function ErrorBlock({
  message,
  onRetry,
  title = "Something went wrong",
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <Notice tone="error" title={title}>
      <p>{message}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </Notice>
  );
}

export function LoadingBlock({ label }: { label: string }) {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className="flex flex-col gap-3 rounded-xl border border-border bg-background p-5"
    >
      <p className="text-sm text-muted-foreground">{label}…</p>
      <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
    </div>
  );
}
