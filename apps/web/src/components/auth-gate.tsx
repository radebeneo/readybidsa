"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { LoadingBlock, Notice } from "@/components/notice";
import { buttonVariants } from "@/components/ui/button";
import { API_NOT_CONFIGURED, isApiConfigured } from "@/lib/api-client";
import { SUPABASE_NOT_CONFIGURED } from "@/lib/supabase-browser";
import { useAuth } from "@/lib/use-auth";

/** Renders `children` only for a signed-in user, with clear states for everything else. */
export function AuthGate({ children }: { children: (session: Session) => ReactNode }) {
  const auth = useAuth();

  if (auth.status === "not-configured") {
    return (
      <Notice tone="warn" title="Integration not configured">
        {SUPABASE_NOT_CONFIGURED}
      </Notice>
    );
  }
  if (!isApiConfigured()) {
    return (
      <Notice tone="warn" title="Integration not configured">
        {API_NOT_CONFIGURED}
      </Notice>
    );
  }
  if (auth.status === "loading") return <LoadingBlock label="Checking your sign-in" />;
  if (auth.status === "signed-out") {
    return (
      <div className="rounded-xl border border-dashed border-border bg-background p-10 text-center">
        <p className="text-sm font-medium">Sign in to continue</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Tenders and their documents are private to your organisation.
        </p>
        <Link href="/login" className={buttonVariants({ className: "mt-4" })}>
          Sign in
        </Link>
      </div>
    );
  }
  return <>{children(auth.session)}</>;
}
