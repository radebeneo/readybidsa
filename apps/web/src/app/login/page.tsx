import type { Metadata } from "next";
import { LoginForm } from "@/components/login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <section className="mx-auto w-full max-w-md">
      <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Sign in to prepare tenders for your organisation.
      </p>
      <div className="mt-6 rounded-xl border border-border bg-background p-6">
        <LoginForm />
      </div>
    </section>
  );
}
