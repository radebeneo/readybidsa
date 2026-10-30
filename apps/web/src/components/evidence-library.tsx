"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { AuthGate } from "@/components/auth-gate";
import { ErrorBlock, LoadingBlock, Notice } from "@/components/notice";
import { ProgressBar } from "@/components/progress-bar";
import { Button } from "@/components/ui/button";
import { api, errorMessage, isAbortError, uploadEvidence, type Loadable } from "@/lib/api-client";
import {
  EVIDENCE_LABELS,
  EVIDENCE_LABEL_NAMES,
  TEXT_STATUS_LABELS,
  evidenceLabelName,
  type EvidenceDocumentOut,
  type EvidenceLabel,
  type EvidenceListOut,
  type OrganisationOut,
  type PageWarningOut,
  type TextStatus,
} from "@/lib/api-types";
import { extractionLabel, formatBytes, formatDateTime, plural } from "@/lib/format";
import { cn } from "@/lib/utils";

export function EvidenceLibrary() {
  // Keyed by user so switching accounts never shows the previous user's data.
  return <AuthGate>{(session) => <OrganisationEvidence key={session.user.id} />}</AuthGate>;
}

function OrganisationEvidence() {
  const [organisations, setOrganisations] = useState<Loadable<OrganisationOut[]>>({
    state: "loading",
  });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.listOrganisations().then(
      (data) => {
        if (!cancelled) setOrganisations({ state: "ready", data });
      },
      (error: unknown) => {
        if (!cancelled) setOrganisations({ state: "error", message: errorMessage(error) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (organisations.state === "loading") return <LoadingBlock label="Loading your organisation" />;
  if (organisations.state === "error") {
    return (
      <ErrorBlock
        message={organisations.message}
        onRetry={() => {
          setOrganisations({ state: "loading" });
          setReloadKey((key) => key + 1);
        }}
      />
    );
  }

  // The API allows one organisation per user in this slice.
  const organisation = organisations.data[0];
  if (!organisation) {
    return (
      <Notice title="Set up your organisation first">
        Company documents belong to an organisation.{" "}
        <Link href="/tenders" className="font-medium underline underline-offset-4">
          Create your organisation on the Tenders page
        </Link>
        , then come back here.
      </Notice>
    );
  }
  return <EvidenceList organisation={organisation} />;
}

type UploadState =
  | { state: "idle" }
  | { state: "uploading"; fileName: string; fraction: number }
  | { state: "done"; document: EvidenceDocumentOut }
  | { state: "error"; message: string };

function EvidenceList({ organisation }: { organisation: OrganisationOut }) {
  const [evidence, setEvidence] = useState<Loadable<EvidenceListOut>>({ state: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.listEvidence(organisation.id).then(
      (data) => {
        if (!cancelled) setEvidence({ state: "ready", data });
      },
      (error: unknown) => {
        if (!cancelled) setEvidence({ state: "error", message: errorMessage(error) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [organisation.id, reloadKey]);

  function reload() {
    setEvidence({ state: "loading" });
    setReloadKey((key) => key + 1);
  }

  function handleUploaded(document: EvidenceDocumentOut) {
    setEvidence((current) =>
      current.state === "ready"
        ? {
            state: "ready",
            data: {
              ...current.data,
              documents: [document, ...current.data.documents.filter((d) => d.id !== document.id)],
            },
          }
        : current,
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <section
        aria-labelledby="evidence-list-heading"
        className="flex flex-col gap-4 rounded-xl border border-border bg-background p-5"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="evidence-list-heading" className="text-base font-semibold">
            Evidence library
          </h2>
          <span className="text-xs text-muted-foreground">{organisation.name}</span>
        </div>

        {evidence.state === "loading" ? <LoadingBlock label="Loading company documents" /> : null}
        {evidence.state === "error" ? <ErrorBlock message={evidence.message} onRetry={reload} /> : null}
        {evidence.state === "ready" ? (
          <>
            <Notice>{evidence.data.notice}</Notice>
            {evidence.data.documents.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-8 text-center">
                <p className="text-sm font-medium">No company documents yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Upload reference letters, company profiles, certificates or declarations. You
                  choose which ones each tender analysis uses.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-border rounded-lg border border-border">
                {evidence.data.documents.map((document) => (
                  <li key={document.id} className="flex flex-col gap-2 px-4 py-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="break-words text-sm font-medium">
                          {document.original_filename}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Your label: {evidenceLabelName(document.evidence_label)} ·{" "}
                          {plural(document.page_count, "page")} · {formatBytes(document.size_bytes)} ·
                          Uploaded {formatDateTime(document.created_at)}
                        </p>
                      </div>
                      <TextStatusBadge status={document.text_status} />
                    </div>
                    <FlaggedPages pages={document.flagged_pages} />
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-muted-foreground">
              One analysis can use up to {evidence.data.max_per_analysis} of these documents.
            </p>
          </>
        ) : null}
      </section>

      <EvidenceUploadForm organisationId={organisation.id} onUploaded={handleUploaded} />
    </div>
  );
}

function EvidenceUploadForm({
  organisationId,
  onUploaded,
}: {
  organisationId: string;
  onUploaded: (document: EvidenceDocumentOut) => void;
}) {
  const controllerRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [label, setLabel] = useState<EvidenceLabel | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [upload, setUpload] = useState<UploadState>({ state: "idle" });

  // Cancel an in-flight upload if the user leaves the page.
  useEffect(() => () => controllerRef.current?.abort(), []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (label === "") {
      setUpload({ state: "error", message: "Choose what kind of document this is." });
      return;
    }
    if (!file) {
      setUpload({ state: "error", message: "Choose a PDF file." });
      return;
    }
    const looksLikePdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!looksLikePdf) {
      setUpload({ state: "error", message: "Choose a PDF file." });
      return;
    }

    const controller = new AbortController();
    controllerRef.current = controller;
    setUpload({ state: "uploading", fileName: file.name, fraction: 0 });
    try {
      const document = await uploadEvidence(
        organisationId,
        file,
        label,
        (fraction) => setUpload({ state: "uploading", fileName: file.name, fraction }),
        controller.signal,
      );
      onUploaded(document);
      setUpload({ state: "done", document });
      setFile(null);
      setLabel("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (error) {
      setUpload(isAbortError(error) ? { state: "idle" } : { state: "error", message: errorMessage(error) });
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }

  const uploading = upload.state === "uploading";

  return (
    <section
      aria-labelledby="evidence-upload-heading"
      className="h-fit rounded-xl border border-border bg-background p-5"
    >
      <h2 id="evidence-upload-heading" className="text-base font-semibold">
        Add a company document
      </h2>
      <form onSubmit={(event) => void handleSubmit(event)} className="mt-4 flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="evidence-label" className="text-sm font-medium">
            Document type
          </label>
          <select
            id="evidence-label"
            required
            disabled={uploading}
            value={label}
            onChange={(event) => setLabel(event.target.value as EvidenceLabel | "")}
            className="h-9 rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
          >
            <option value="">Choose a type…</option>
            {EVIDENCE_LABELS.map((value) => (
              <option key={value} value={value}>
                {EVIDENCE_LABEL_NAMES[value]}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted-foreground">
            This is your own description of the file. ReadyBid does not check it.
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="evidence-pdf" className="text-sm font-medium">
            PDF file
          </label>
          <input
            ref={fileInputRef}
            id="evidence-pdf"
            type="file"
            accept="application/pdf,.pdf"
            disabled={uploading}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="text-sm file:mr-3 file:rounded-lg file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm file:font-medium hover:file:bg-muted disabled:opacity-50"
          />
          <p className="text-xs text-muted-foreground">
            English, text-readable PDFs only. Pages without extractable text (such as scans) are
            flagged and cannot count as support.
          </p>
        </div>

        {upload.state === "uploading" ? (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="truncate">
                {upload.fraction >= 1 ? "Checking" : "Uploading"} {upload.fileName}…
              </span>
              <Button variant="ghost" size="sm" onClick={() => controllerRef.current?.abort()}>
                Cancel
              </Button>
            </div>
            <ProgressBar value={upload.fraction * 100} label={`Uploading ${upload.fileName}`} />
          </div>
        ) : null}
        {upload.state === "done" ? (
          <Notice tone={upload.document.text_status === "readable" ? "success" : "warn"}>
            Uploaded {upload.document.original_filename}.{" "}
            {upload.document.text_status === "readable"
              ? "Its text was read."
              : `${TEXT_STATUS_LABELS[upload.document.text_status]}: only readable pages can be matched.`}
          </Notice>
        ) : null}
        {upload.state === "error" ? (
          <Notice tone="error" title="Upload failed">
            {upload.message}
          </Notice>
        ) : null}

        <Button type="submit" disabled={uploading}>
          {uploading ? "Uploading…" : "Upload document"}
        </Button>
      </form>
    </section>
  );
}

const TEXT_STATUS_TONES: Record<TextStatus, string> = {
  readable:
    "bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  partly_readable: "bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  unreadable: "bg-red-50 text-red-900 dark:bg-red-950 dark:text-red-200",
  not_extracted: "bg-muted text-foreground",
};

/** Whether ReadyBid could read the document's text. Says nothing about its contents. */
export function TextStatusBadge({ status }: { status: TextStatus }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
        TEXT_STATUS_TONES[status] ?? TEXT_STATUS_TONES.not_extracted,
      )}
    >
      {TEXT_STATUS_LABELS[status] ?? status}
    </span>
  );
}

/** Pages whose text could not be read cleanly. They are kept and listed, never dropped. */
export function FlaggedPages({ pages }: { pages: PageWarningOut[] }) {
  if (pages.length === 0) return null;
  return (
    <ul className="list-disc pl-5 text-xs text-amber-900 dark:text-amber-200">
      {pages.map((warning) => (
        <li key={warning.page_number}>
          Page {warning.page_number}: {extractionLabel(warning.status)}
          {warning.note ? ` (${warning.note})` : ""}
        </li>
      ))}
    </ul>
  );
}
