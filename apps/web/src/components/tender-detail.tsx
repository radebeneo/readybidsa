"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { AuthGate } from "@/components/auth-gate";
import { ChecklistView } from "@/components/checklist-view";
import { EvidenceSelector } from "@/components/evidence-selector";
import { ErrorBlock, LoadingBlock, Notice } from "@/components/notice";
import { ProgressBar } from "@/components/progress-bar";
import { SourceDrawer, type SourceRef } from "@/components/source-drawer";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  ApiError,
  api,
  errorMessage,
  isAbortError,
  safeHttpUrl,
  uploadDocument,
  type Loadable,
} from "@/lib/api-client";
import {
  RUN_STATUS_LABELS,
  isActiveStatus,
  type AnalysisRunOut,
  type DocumentOut,
  type JobOut,
  type RunStatus,
  type TenderDetailOut,
} from "@/lib/api-types";
import { formatBytes, formatDateTime, plural } from "@/lib/format";

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_FAILURES = 5;

export function TenderDetail() {
  const params = useParams<{ id: string }>();
  const tenderId = typeof params.id === "string" ? params.id : "";

  return (
    <div className="flex flex-col gap-6">
      <Link href="/tenders" className="w-fit text-sm text-muted-foreground hover:text-foreground">
        ← All tenders
      </Link>
      <AuthGate>
        {(session) =>
          tenderId ? (
            // Keyed so a different user or tender always starts from a clean state.
            <TenderWorkspace key={`${session.user.id}:${tenderId}`} tenderId={tenderId} />
          ) : (
            <Notice tone="error">Not found.</Notice>
          )
        }
      </AuthGate>
    </div>
  );
}


function TenderWorkspace({ tenderId }: { tenderId: string }) {
  const [detail, setDetail] = useState<Loadable<TenderDetailOut>>({ state: "loading" });
  const [detailKey, setDetailKey] = useState(0);
  const [analysis, setAnalysis] = useState<AnalysisRunOut | null>(null);
  const [job, setJob] = useState<JobOut | null>(null);
  const [pollFailures, setPollFailures] = useState(0);
  const [pollError, setPollError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [source, setSource] = useState<(SourceRef & { open: boolean }) | null>(null);
  // The user's explicit choice of company evidence. Empty means no evidence matching.
  const [evidenceSelection, setEvidenceSelection] = useState<string[]>([]);

  // Load the tender and resume its latest analysis, if any.
  useEffect(() => {
    let cancelled = false;
    api.getTender(tenderId).then(
      (data) => {
        if (cancelled) return;
        setDetail({ state: "ready", data });
        setAnalysis(data.latest_analysis);
        setJob(data.latest_job);
        setPollFailures(0);
        setPollError(null);
      },
      (error: unknown) => {
        if (!cancelled) setDetail({ state: "error", message: errorMessage(error) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [tenderId, detailKey]);

  // Poll the job while it is queued or running. Each response is a new object, which
  // schedules the next poll. Failures back off and stop after MAX_POLL_FAILURES.
  useEffect(() => {
    if (!job || !isActiveStatus(job.status) || pollFailures >= MAX_POLL_FAILURES) return;
    const controller = new AbortController();
    const timer = window.setTimeout(
      () => {
        api.getJob(job.id, controller.signal).then(
          (next) => {
            setJob(next);
            setPollFailures(0);
            setPollError(null);
          },
          (error: unknown) => {
            if (isAbortError(error)) return;
            setPollError(errorMessage(error));
            const permanent =
              error instanceof ApiError && (error.status === 401 || error.status === 404);
            setPollFailures((count) => (permanent ? MAX_POLL_FAILURES : count + 1));
          },
        );
      },
      POLL_INTERVAL_MS * (pollFailures + 1),
    );
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [job, pollFailures]);

  const runId = job?.analysis_run_id ?? analysis?.id ?? null;
  const runStatus: RunStatus | null = job?.status ?? analysis?.status ?? null;
  const resultsRunId =
    runId !== null && (runStatus === "completed" || runStatus === "partial") ? runId : null;

  async function startAnalysis(documentId: string) {
    setStarting(true);
    setStartError(null);
    try {
      const out = await api.startAnalysis(tenderId, documentId, evidenceSelection);
      setAnalysis(out.analysis);
      setJob(out.job);
      setPollFailures(0);
      setPollError(null);
    } catch (error) {
      setStartError(errorMessage(error));
    } finally {
      setStarting(false);
    }
  }

  function handleUploaded(document: DocumentOut) {
    setDetail((current) =>
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

  function reloadDetail() {
    setDetail({ state: "loading" });
    setDetailKey((key) => key + 1);
  }

  if (detail.state === "loading") return <LoadingBlock label="Loading tender" />;
  if (detail.state === "error") return <ErrorBlock message={detail.message} onRetry={reloadDetail} />;

  const { tender, documents } = detail.data;
  const analysisActive = runStatus !== null && isActiveStatus(runStatus);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{tender.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {tender.reference ? `${tender.reference} · ` : ""}Created {formatDateTime(tender.created_at)}
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <DocumentsPanel
          tenderId={tenderId}
          documents={documents}
          analysedDocumentId={analysis?.document_id ?? null}
          analysisActive={analysisActive}
          starting={starting}
          onUploaded={handleUploaded}
          onAnalyse={(documentId) => void startAnalysis(documentId)}
        />
        <AnalysisPanel
          job={job}
          runStatus={runStatus}
          analysisError={analysis?.error ?? null}
          startError={startError}
          pollError={pollError}
          pollStopped={pollFailures >= MAX_POLL_FAILURES}
          onResumePolling={() => {
            setPollError(null);
            setPollFailures(0);
          }}
          onRefresh={reloadDetail}
        />
      </div>

      <EvidenceSelector
        organisationId={tender.organisation_id}
        selected={evidenceSelection}
        onChange={setEvidenceSelection}
        disabled={analysisActive || starting}
      />

      {resultsRunId !== null ? (
        <ChecklistView
          key={resultsRunId}
          runId={resultsRunId}
          onOpenSource={(id) => setSource({ kind: "tender", id, open: true })}
          onOpenEvidenceSource={(id) => setSource({ kind: "evidence", id, open: true })}
        />
      ) : null}

      <SourceDrawer
        source={source ? { kind: source.kind, id: source.id } : null}
        open={source?.open ?? false}
        onOpenChange={(open) => setSource((current) => (current ? { ...current, open } : null))}
      />
    </div>
  );
}

type UploadState =
  | { state: "idle" }
  | { state: "uploading"; fileName: string; fraction: number }
  | { state: "done"; fileName: string }
  | { state: "error"; message: string };

function DocumentsPanel({
  tenderId,
  documents,
  analysedDocumentId,
  analysisActive,
  starting,
  onUploaded,
  onAnalyse,
}: {
  tenderId: string;
  documents: DocumentOut[];
  analysedDocumentId: string | null;
  analysisActive: boolean;
  starting: boolean;
  onUploaded: (document: DocumentOut) => void;
  onAnalyse: (documentId: string) => void;
}) {
  const controllerRef = useRef<AbortController | null>(null);
  const [upload, setUpload] = useState<UploadState>({ state: "idle" });

  // Cancel an in-flight upload if the user leaves the page.
  useEffect(() => () => controllerRef.current?.abort(), []);

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const looksLikePdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!looksLikePdf) {
      setUpload({ state: "error", message: "Choose a PDF file." });
      return;
    }

    const controller = new AbortController();
    controllerRef.current = controller;
    setUpload({ state: "uploading", fileName: file.name, fraction: 0 });
    try {
      const document = await uploadDocument(
        tenderId,
        file,
        (fraction) => setUpload({ state: "uploading", fileName: file.name, fraction }),
        controller.signal,
      );
      onUploaded(document);
      setUpload({ state: "done", fileName: document.original_filename });
    } catch (error) {
      setUpload(isAbortError(error) ? { state: "idle" } : { state: "error", message: errorMessage(error) });
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }

  const uploading = upload.state === "uploading";

  return (
    <section
      aria-labelledby="documents-heading"
      className="flex flex-col gap-4 rounded-xl border border-border bg-background p-5"
    >
      <h2 id="documents-heading" className="text-base font-semibold">
        Tender documents
      </h2>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="tender-pdf" className="text-sm font-medium">
          Upload tender PDF
        </label>
        <input
          id="tender-pdf"
          type="file"
          accept="application/pdf,.pdf"
          disabled={uploading}
          onChange={(event) => void handleFile(event)}
          className="text-sm file:mr-3 file:rounded-lg file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm file:font-medium hover:file:bg-muted disabled:opacity-50"
        />
        <p className="text-xs text-muted-foreground">
          English, text-readable PDFs only. Pages without extractable text (such as scans) are
          flagged, not read. The server sets the size and page limits (15 MB and 100 pages by
          default).
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
        <Notice tone="success">
          Uploaded {upload.fileName}. Choose Analyse to extract its requirements.
        </Notice>
      ) : null}
      {upload.state === "error" ? (
        <Notice tone="error" title="Upload failed">
          {upload.message}
        </Notice>
      ) : null}

      {documents.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          No documents uploaded yet.
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {documents.map((document) => (
            <li key={document.id} className="flex flex-col gap-2 px-4 py-3">
              <div>
                <p className="break-words text-sm font-medium">{document.original_filename}</p>
                <p className="text-xs text-muted-foreground">
                  Version {document.version} · {plural(document.page_count, "page")} ·{" "}
                  {formatBytes(document.size_bytes)} · Uploaded {formatDateTime(document.created_at)}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  disabled={analysisActive || starting}
                  onClick={() => onAnalyse(document.id)}
                >
                  {analysedDocumentId === document.id ? "Analyse again" : "Analyse"}
                </Button>
                <DocumentLink documentId={document.id} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DocumentLink({ documentId }: { documentId: string }) {
  const [link, setLink] = useState<Loadable<string> | null>(null);

  async function fetchLink() {
    setLink({ state: "loading" });
    try {
      const file = await api.getDocumentFile(documentId);
      const url = safeHttpUrl(file.signed_url);
      setLink(url ? { state: "ready", data: url } : { state: "error", message: "The API returned an invalid file link." });
    } catch (error) {
      setLink({ state: "error", message: errorMessage(error) });
    }
  }

  if (link?.state === "ready") {
    // Signed links are short-lived, so the link is discarded once used.
    return (
      <a
        href={link.data}
        target="_blank"
        rel="noopener noreferrer"
        onClick={() => setLink(null)}
        className={buttonVariants({ variant: "outline", size: "sm" })}
      >
        Open PDF
      </a>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-2">
      <Button
        variant="ghost"
        size="sm"
        disabled={link?.state === "loading"}
        onClick={() => void fetchLink()}
      >
        {link?.state === "loading" ? "Getting link…" : "View PDF"}
      </Button>
      {link?.state === "error" ? (
        <span role="alert" className="text-xs text-red-700 dark:text-red-300">
          {link.message}
        </span>
      ) : null}
    </span>
  );
}

function AnalysisPanel({
  job,
  runStatus,
  analysisError,
  startError,
  pollError,
  pollStopped,
  onResumePolling,
  onRefresh,
}: {
  job: JobOut | null;
  runStatus: RunStatus | null;
  analysisError: string | null;
  startError: string | null;
  pollError: string | null;
  pollStopped: boolean;
  onResumePolling: () => void;
  onRefresh: () => void;
}) {
  return (
    <section
      aria-labelledby="analysis-heading"
      aria-live="polite"
      className="flex flex-col gap-4 rounded-xl border border-border bg-background p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="analysis-heading" className="text-base font-semibold">
          Analysis
        </h2>
        {runStatus ? (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
            {RUN_STATUS_LABELS[runStatus]}
          </span>
        ) : null}
      </div>

      {startError ? (
        <Notice tone="error" title="Could not start the analysis">
          {startError}
        </Notice>
      ) : null}

      {runStatus === null ? (
        <p className="text-sm text-muted-foreground">
          No analysis yet. Upload the tender PDF, then choose Analyse.
        </p>
      ) : null}

      {runStatus !== null && isActiveStatus(runStatus) ? (
        job ? (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="capitalize">{job.stage}</span>
              <span className="text-muted-foreground">{Math.round(job.progress)}%</span>
            </div>
            <ProgressBar value={job.progress} label="Analysis progress" />
            {job.attempts > 1 ? (
              <p className="text-xs text-muted-foreground">Attempt {job.attempts}</p>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-col gap-2 text-sm text-muted-foreground">
            <p>The analysis is in progress, but its job status is not available yet.</p>
            <Button variant="outline" size="sm" className="w-fit" onClick={onRefresh}>
              Refresh
            </Button>
          </div>
        )
      ) : null}

      {pollError && !pollStopped ? (
        <Notice tone="warn">Lost contact with the API ({pollError}). Retrying…</Notice>
      ) : null}
      {pollStopped && runStatus !== null && isActiveStatus(runStatus) ? (
        <Notice tone="error" title="Stopped checking progress">
          <p>{pollError ?? "Progress updates failed repeatedly."}</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={onResumePolling}>
            Check again
          </Button>
        </Notice>
      ) : null}

      {runStatus === "completed" ? (
        <Notice tone="success">The analysis finished. Review the requirements below.</Notice>
      ) : null}
      {runStatus === "partial" ? (
        <Notice tone="warn" title="Partial results">
          Some parts of the document could not be analysed. The requirements below are
          incomplete.
        </Notice>
      ) : null}
      {runStatus === "failed" ? (
        <Notice tone="error" title="The analysis failed">
          <p>{job?.error ?? analysisError ?? "No requirements were produced."}</p>
          <p className="mt-1">You can start the analysis again from the document list.</p>
        </Notice>
      ) : null}

      <p className="text-xs text-muted-foreground">
        Extracted requirements are a preparation aid, not legal advice or an eligibility check.
      </p>
    </section>
  );
}
