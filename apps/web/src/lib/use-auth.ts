import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getSupabase, isSupabaseConfigured } from "@/lib/supabase-browser";

export type AuthState =
  | { status: "not-configured" }
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; session: Session };

/** Current Supabase sign-in state. Client Components only. */
export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>(() =>
    isSupabaseConfigured() ? { status: "loading" } : { status: "not-configured" },
  );

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return;
    // Fires INITIAL_SESSION straight away, then on every sign-in, sign-out and token refresh.
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setState(session ? { status: "signed-in", session } : { status: "signed-out" });
    });
    return () => data.subscription.unsubscribe();
  }, []);

  return state;
}
