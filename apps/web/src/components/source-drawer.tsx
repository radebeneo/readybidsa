"use client";

import { Dialog } from "@base-ui/react/dialog";
import { useEffect, useState } from "react";
import { ErrorBlock, LoadingBlock, Notice } from "@/components/notice";
import { buttonVariants } from "@/components/ui/button";
import { api, errorMessage, safeHttpUrl, type Loadable } from "@/lib/api-client";
import { evidenceLabelName } from "@/lib/api-types";
import { extractionLabel, formatDuration } from "@/lib/format";

/**
 * "tender": the tender passage a requirement was extracted from.
 * "evidence": a candidate passage in one of the company's own documents.
 */
export type SourceKind = "tender" | "evidence";

export type SourceRef = { kind: SourceKind; id: string };

type PassageView = {
  documentFilename: string;
  documentVersion: number;
  evidenceLabel: string | null;
  pageNumber: number;
  quote: string;
  relationship: string | null;
  extractionStatus: string;
  extractionNote: string | null;
  signedUrl: string;
  expiresInSeconds: number;
};

async function loadPassage(kind: SourceKind, id: string): Promise<PassageView> {
  if (kind === "evidence") {
    const data = await api.getEvidenceSource(id);
    return {
      documentFilename: data.document_filename,
      documentVersion: data.document_version,
      evidenceLabel: data.evidence_label,
      pageNumber: data.page_number,
      quote: data.quote,
      relationship: data.relationship,
      extractionStatus: data.extraction_status,
      extractionNote: data.extraction_note,
      signedUrl: data.signed_url,
      expiresInSeconds: data.expires_in_seconds,
    };
  }
  const data = await api.getSource(id);
  return {
    documentFilename: data.document_filename,
    documentVersion: data.document_version,
    evidenceLabel: null,
    pageNumber: data.page_number,
    quote: data.quote,
    relationship: null,
    extractionStatus: data.extraction_status,
    extractionNote: data.extraction_note,
    signedUrl: data.signed_url,
    expiresInSeconds: data.expires_in_seconds,
  };
}

/**
 * Side drawer showing one cited passage. `source` is kept while the drawer closes so the
 * content stays visible during the exit animation.
 */
export function SourceDrawer({
  source,
  open,
  onOpenChange,
}: {
  source: SourceRef | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const evidence = source?.kind === "evidence";
  return (
    <Dialog.Root open={open && source !== null} onOpenChange={(next) => onOpenChange(next)}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 bg-black/40 transition-opacity duration-200 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0" />
        <Dialog.Popup className="fixed inset-y-0 right-0 flex w-full max-w-lg flex-col gap-4 overflow-y-auto border-l border-border bg-background p-6 shadow-xl outline-none transition-transform duration-200 data-[ending-style]:translate-x-full data-[starting-style]:translate-x-full">
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="text-base font-semibold">
              {evidence ? "Candidate evidence passage" : "Source passage"}
            </Dialog.Title>
            <Dialog.Close className={buttonVariants({ variant: "ghost", size: "sm" })}>
              Close
            </Dialog.Close>
          </div>
          <Dialog.Description className="text-sm text-muted-foreground">
            {evidence
              ? "A passage from one of your company documents that may relate to this requirement, with a link to its page in the PDF."
              : "The exact passage this requirement was extracted from, with a link to its page in the tender PDF."}
          </Dialog.Description>
          {source ? (
            <SourceDetails key={`${source.kind}:${source.id}`} kind={source.kind} id={source.id} />
          ) : null}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function SourceDetails({ kind, id }: { kind: SourceKind; id: string }) {
  const [passage, setPassage] = useState<Loadable<PassageView>>({ state: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    loadPassage(kind, id).then(
      (data) => {
        if (!cancelled) setPassage({ state: "ready", data });
      },
      (error: unknown) => {
        if (!cancelled) setPassage({ state: "error", message: errorMessage(error) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [kind, id, reloadKey]);

  if (passage.state === "loading") return <LoadingBlock label="Loading source" />;
  if (passage.state === "error") {
    return (
      <ErrorBlock
        message={passage.message}
        onRetry={() => {
          setPassage({ state: "loading" });
          setReloadKey((key) => key + 1);
        }}
      />
    );
  }

  const data = passage.data;
  const evidence = kind === "evidence";
  const fileUrl = safeHttpUrl(data.signedUrl);
  return (
    <div className="flex flex-col gap-4">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Document</dt>
        <dd className="break-words">
          {data.documentFilename} (version {data.documentVersion})
        </dd>
        {evidence ? (
          <>
            <dt className="text-muted-foreground">Your label</dt>
            <dd>{evidenceLabelName(data.evidenceLabel)}</dd>
          </>
        ) : null}
        <dt className="text-muted-foreground">Page</dt>
        <dd>{data.pageNumber}</dd>
      </dl>

      {data.extractionStatus !== "ok" ? (
        <Notice tone="warn" title="Page text may be incomplete">
          This page was flagged during text extraction: {extractionLabel(data.extractionStatus)}
          {data.extractionNote ? ` (${data.extractionNote})` : ""}. Check it in the PDF.
          {evidence ? " Passages from flagged pages cannot count as support." : ""}
        </Notice>
      ) : null}

      <blockquote
        className={
          evidence
            ? "whitespace-pre-wrap rounded-lg border-l-4 border-sky-400 bg-muted/50 px-4 py-3 text-sm"
            : "whitespace-pre-wrap rounded-lg border-l-4 border-primary bg-muted/50 px-4 py-3 text-sm"
        }
      >
        {data.quote}
      </blockquote>

      {evidence && data.relationship ? (
        <div className="flex flex-col gap-1 text-sm">
          <p className="text-xs font-medium text-muted-foreground">
            Suggested relationship (AI, review required)
          </p>
          <p className="whitespace-pre-wrap">{data.relationship}</p>
        </div>
      ) : null}

      {fileUrl ? (
        <div className="flex flex-col gap-1">
          <a
            href={`${fileUrl}#page=${data.pageNumber}`}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonVariants({ variant: "outline" })}
          >
            Open page {data.pageNumber} in the PDF
          </a>
          <p className="text-xs text-muted-foreground">
            This private link expires in about {formatDuration(data.expiresInSeconds)}. Reopen the
            source to get a new one.
          </p>
        </div>
      ) : (
        <Notice tone="error">The API returned an invalid file link.</Notice>
      )}

      <p className="text-xs text-muted-foreground">
        {evidence
          ? "ReadyBid does not check whether this document is genuine, signed, current or sufficient for the tender. Confirm it yourself."
          : "Always confirm the requirement against the official tender document."}
      </p>
    </div>
  );
}
