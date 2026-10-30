// Browser-side Supabase client. Used for sign-in only: all data goes through the ReadyBid API.
// It uses the public anon (publishable) key. Never put the service role key in the web app.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// NEXT_PUBLIC_* values are inlined at build time, so they must be referenced literally.
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL ?? "").trim();
const supabaseAnonKey = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "").trim();

export const SUPABASE_NOT_CONFIGURED =
  "Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in apps/web/.env.local, then restart or rebuild the web app.";

let client: SupabaseClient | null = null;

export function isSupabaseConfigured(): boolean {
  return supabaseUrl !== "" && supabaseAnonKey !== "";
}

/** The shared browser client. Returns null on the server or when Supabase is not configured. */
export function getSupabase(): SupabaseClient | null {
  if (typeof window === "undefined" || !isSupabaseConfigured()) return null;
  client ??= createClient(supabaseUrl, supabaseAnonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });
  return client;
}
