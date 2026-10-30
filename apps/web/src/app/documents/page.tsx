import type { Metadata } from "next";
import { EvidenceLibrary } from "@/components/evidence-library";

export const metadata: Metadata = { title: "Company documents" };

export default function DocumentsPage() {
  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Company documents</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Store the supporting documents you reuse across tenders, such as reference letters,
          company profiles, certificates and declarations. Each analysis only uses the documents
          you select for it.
        </p>
      </div>
      <EvidenceLibrary />
    </section>
  );
}
