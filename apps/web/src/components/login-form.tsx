"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { LoadingBlock, Notice } from "@/components/notice";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SUPABASE_NOT_CONFIGURED, getSupabase } from "@/lib/supabase-browser";
import { useAuth } from "@/lib/use-auth";

type Mode = "sign-in" | "sign-up";

export function LoginForm() {
  const auth = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  if (auth.status === "not-configured") {
    return (
      <Notice tone="warn" title="Integration not configured">
        {SUPABASE_NOT_CONFIGURED}
      </Notice>
    );
  }
  if (auth.status === "loading") return <LoadingBlock label="Checking your sign-in" />;
  if (auth.status === "signed-in") {
    return (
      <div className="flex flex-col gap-4">
        <Notice tone="success" title="You are signed in">
          Signed in as {auth.session.user.email ?? "your account"}.
        </Notice>
        <Link href="/tenders" className={buttonVariants()}>
          Go to tenders
        </Link>
      </div>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const supabase = getSupabase();
    if (!supabase) return;
    setPending(true);
    setMessage(null);
    try {
      if (mode === "sign-in") {
        const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
        if (error) {
          setMessage({ tone: "error", text: error.message });
          return;
        }
        router.push("/tenders");
        return;
      }
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: { emailRedirectTo: `${window.location.origin}/tenders` },
      });
      if (error) {
        setMessage({ tone: "error", text: error.message });
        return;
      }
      if (data.session) {
        router.push("/tenders");
      } else {
        setMessage({
          tone: "success",
          text: "Check your email for a confirmation link, then sign in.",
        });
        setMode("sign-in");
      }
    } catch {
      setMessage({ tone: "error", text: "Could not reach Supabase. Check your connection and try again." });
    } finally {
      setPending(false);
    }
  }

  const signingIn = mode === "sign-in";
  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="login-email" className="text-sm font-medium">
          Email
        </label>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="login-password" className="text-sm font-medium">
          Password
        </label>
        <Input
          id="login-password"
          type="password"
          autoComplete={signingIn ? "current-password" : "new-password"}
          required
          minLength={signingIn ? undefined : 8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {signingIn ? null : (
          <p className="text-xs text-muted-foreground">Use at least 8 characters.</p>
        )}
      </div>

      {message ? (
        <Notice tone={message.tone}>{message.text}</Notice>
      ) : null}

      <Button type="submit" size="lg" disabled={pending}>
        {pending ? "Please wait…" : signingIn ? "Sign in" : "Create account"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        {signingIn ? "New to ReadyBid SA?" : "Already have an account?"}{" "}
        <button
          type="button"
          className="font-medium text-foreground underline-offset-4 hover:underline"
          onClick={() => {
            setMode(signingIn ? "sign-up" : "sign-in");
            setMessage(null);
          }}
        >
          {signingIn ? "Create an account" : "Sign in instead"}
        </button>
      </p>
    </form>
  );
}
