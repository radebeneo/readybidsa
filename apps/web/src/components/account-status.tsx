"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { getSupabase } from "@/lib/supabase-browser";
import { useAuth } from "@/lib/use-auth";

export function AccountStatus() {
  const auth = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);

  if (auth.status === "not-configured" || auth.status === "loading") return null;

  if (auth.status === "signed-out") {
    return (
      <Link href="/login" className={buttonVariants({ variant: "outline", size: "sm" })}>
        Sign in
      </Link>
    );
  }

  async function signOut() {
    const supabase = getSupabase();
    if (!supabase) return;
    setPending(true);
    try {
      await supabase.auth.signOut();
      router.push("/login");
    } finally {
      setPending(false);
    }
  }

  const email = auth.session.user.email ?? "Signed in";
  return (
    <div className="flex items-center gap-2">
      <span className="max-w-48 truncate text-xs text-muted-foreground" title={email}>
        {email}
      </span>
      <Button variant="ghost" size="sm" disabled={pending} onClick={() => void signOut()}>
        Sign out
      </Button>
    </div>
  );
}
