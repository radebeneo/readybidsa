import type { Metadata } from "next";
import { TendersWorkspace } from "@/components/tenders-workspace";

export const metadata: Metadata = { title: "Tenders" };

export default function TendersPage() {
  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Tenders</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Create a tender workspace, upload its PDF and review the extracted requirements.
        </p>
      </div>
      <TendersWorkspace />
    </section>
  );
}
