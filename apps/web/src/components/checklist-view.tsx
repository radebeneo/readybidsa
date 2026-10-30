"use client";

import { Fragment, useEffect, useState, type FormEvent } from "react";
import { TextStatusBadge } from "@/components/evidence-library";
import { ErrorBlock, LoadingBlock, Notice } from "@/components/notice";
import { CoverageSummary } from "@/components/requirements-view";
import { Button } from "@/components/ui/button";
import {
  api,
  downloadChecklistExport,
  errorMessage,
  type ExportFormat,
  type Loadable,
} from "@/lib/api-client";
import {
  DECISIONS,
  DECISION_LABELS,
  checklistStatusLabel,
  decisionLabel,
  evidenceLabelName,
  type ChecklistItemOut,
  type ChecklistOut,
  type Decision,
  type DecisionOut,
  type ReviewIndicatorsOut,
  type SelectedEvidenceOut,
} from "@/lib/api-types";
import { formatDateTime, humanise, plural } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Matches the API limit on review notes. */
const NOTES_MAX_LENGTH = 2000;

type Filter = "all" | "missing_evidence" | "potential_blockers" | "unresolved";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "missing_evidence", label: "Missing evidence" },
  { value: "potential_blockers", label: "Potential blockers" },
  { value: "unresolved", label: "Unresolved" },
];

const AMBER =
  "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200";

const STATUS_CLASSES: Record<string, string> = {
  evidence_found_review_required:
    "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-200",
  missing_evidence: AMBER,
  ambiguous_requirement: AMBER,
  extraction_incomplete: AMBER,
  potential_blocker_review_required:
    "border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-200",
  human_reviewed:
    "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
};

const NEUTRAL_STATUS = "border-border bg-muted/50 text-foreground";

function isUnresolved(item: ChecklistItemOut): boolean {
  return item.decision === null || item.decision.decision === "unresolved";
}

function matchesFilter(item: ChecklistItemOut, filter: Filter): boolean {
  const aiStatus = item.assessment?.ai_status ?? null;
  switch (filter) {
    case "missing_evidence":
      return aiStatus === "missing_evidence";
    case "potential_blockers":
      return aiStatus === "potential_blocker_review_required";
    case "unresolved":
      return isUnresolved(item);
    default:
      return true;
  }
}

function asDecision(value: string | undefined): Decision {
  return value !== undefined && (DECISIONS as readonly string[]).includes(value)
    ? (value as Decision)
    : "unresolved";
}

function shortId(id: string): string {
  return id.slice(0, 8);
}

/** Show a saved decision straight away, before the checklist is re-read from the API. */
function withDecision(data: ChecklistOut, saved: DecisionOut): ChecklistOut {
  return {
    ...data,
    items: data.items.map((item) =>
      item.requirement.id === saved.requirement_id
        ? { ...item, decision: saved, decision_history: [...item.decision_history, saved] }
        : item,
    ),
  };
}

/**
 * Review checklist for one analysis run: requirements, candidate evidence and the reviewer's
 * decisions. AI statuses and human decisions are shown separately. There is deliberately no
 * readiness score, compliance percentage or "ready to submit" verdict.
 */
export function ChecklistView({
  runId,
  onOpenSource,
  onOpenEvidenceSource,
}: {
  runId: string;
  onOpenSource: (sourceId: string) => void;
  onOpenEvidenceSource: (sourceId: string) => void;
}) {
  const [checklist, setChecklist] = useState<Loadable<ChecklistOut>>({ state: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [filter, setFilter] = useState<Filter>("all");
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.getChecklist(runId).then(
      (data) => {
        if (!cancelled) setChecklist({ state: "ready", data });
      },
      (error: unknown) => {
        if (!cancelled) setChecklist({ state: "error", message: errorMessage(error) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [runId, reloadKey]);

  function handleSaved(saved: DecisionOut) {
    setChecklist((current) =>
      current.state === "ready" ? { state: "ready", data: withDecision(current.data, saved) } : current,
    );
    // Re-read so statuses and review indicators come from the server.
    api.getChecklist(runId).then(
      (data) => {
        setChecklist({ state: "ready", data });
        setSyncError(null);
      },
      (error: unknown) => {
        setSyncError(
          `Your decision was saved, but the checklist could not be refreshed: ${errorMessage(error)}`,
        );
      },
    );
  }

  if (checklist.state === "loading") return <LoadingBlock label="Loading checklist" />;
  if (checklist.state === "error") {
    return (
      <ErrorBlock
        title="Could not load the checklist"
        message={checklist.message}
        onRetry={() => {
          setChecklist({ state: "loading" });
          setReloadKey((key) => key + 1);
        }}
      />
    );
  }

  const data = checklist.data;
  const { analysis, document: tenderDocument } = data;
  const items = [...data.items].sort((a, b) => a.requirement.position - b.requirement.position);
  const visible = items.filter((item) => matchesFilter(item, filter));
  const counts: Record<Filter, number> = {
    all: items.length,
    missing_evidence: items.filter((item) => matchesFilter(item, "missing_evidence")).length,
    potential_blockers: items.filter((item) => matchesFilter(item, "potential_blockers")).length,
    unresolved: items.filter((item) => matchesFilter(item, "unresolved")).length,
  };
  const analysedAt = analysis.finished_at ?? analysis.started_at ?? analysis.created_at;

  return (
    <section
      aria-labelledby="checklist-heading"
      className="flex flex-col gap-4 rounded-xl border border-border bg-background p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="checklist-heading" className="text-base font-semibold">
          Requirements checklist
        </h2>
        <span className="text-xs text-muted-foreground">
          {tenderDocument.original_filename} · version {tenderDocument.version} · analysed{" "}
          {formatDateTime(analysedAt)}
        </span>
      </div>

      {data.notice ? <Notice>{data.notice}</Notice> : null}
      <MatchingNotice checklist={data} />
      <CoverageSummary coverage={data.coverage} />
      <ReviewIndicators indicators={data.indicators} />
      <SelectedEvidenceList evidence={data.evidence} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Filter requirements" className="flex flex-wrap gap-1">
          {FILTERS.map((option) => (
            <Button
              key={option.value}
              variant={filter === option.value ? "default" : "outline"}
              size="sm"
              aria-pressed={filter === option.value}
              onClick={() => setFilter(option.value)}
            >
              {option.label} ({counts[option.value]})
            </Button>
          ))}
        </div>
        <ExportButtons runId={runId} />
      </div>

      {syncError ? <Notice tone="warn">{syncError}</Notice> : null}

      {items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-8 text-center">
          <p className="text-sm font-medium">No verified requirements</p>
          <p className="mt-1 text-sm text-muted-foreground">
            No requirement could be matched to a quoted passage in the tender. Review the tender PDF
            directly.
          </p>
        </div>
      ) : visible.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          No requirements match this filter.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[64rem] text-left text-sm">
            <caption className="sr-only">
              Review checklist for {tenderDocument.original_filename}
            </caption>
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">
                  Requirement
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Category
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Current assessment
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Matched documents
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Proposed next action
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Source
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Review
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {visible.map((item) => (
                <ChecklistRow
                  key={item.requirement.id}
                  number={items.indexOf(item) + 1}
                  item={item}
                  runId={runId}
                  expanded={openRow === item.requirement.id}
                  onToggle={() =>
                    setOpenRow((current) =>
                      current === item.requirement.id ? null : item.requirement.id,
                    )
                  }
                  onSaved={handleSaved}
                  onOpenSource={onOpenSource}
                  onOpenEvidenceSource={onOpenEvidenceSource}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-md border px-2 py-0.5 text-xs font-medium",
        STATUS_CLASSES[status] ?? NEUTRAL_STATUS,
      )}
    >
      {checklistStatusLabel(status)}
    </span>
  );
}

function MatchingNotice({ checklist }: { checklist: ChecklistOut }) {
  const { analysis } = checklist;
  const status: string = analysis.matching_status;
  if (status === "not_requested") {
    return (
      <Notice title="No company evidence compared">
        No company documents were selected for this analysis, so requirements are listed without
        evidence matching. Select documents above and run a new analysis to compare them.
      </Notice>
    );
  }
  if (status === "failed") {
    return (
      <Notice tone="error" title="Evidence matching failed">
        {analysis.matching_error ?? "The selected company documents could not be compared."} The
        requirements are still listed. Review the evidence yourself or run a new analysis.
      </Notice>
    );
  }
  if (analysis.matching_requirements_failed > 0) {
    return (
      <Notice tone="warn" title="Evidence matching incomplete">
        {plural(analysis.matching_requirements_failed, "requirement")} could not be compared with the
        selected documents. They show as not assessed.
      </Notice>
    );
  }
  return null;
}

function ReviewIndicators({ indicators }: { indicators: ReviewIndicatorsOut }) {
  const entries: { label: string; value: number }[] = [
    { label: "Requirements", value: indicators.requirements_total },
    { label: "Unresolved", value: indicators.unresolved },
    { label: "Potential blockers", value: indicators.potential_blockers },
    { label: "Missing evidence", value: indicators.missing_evidence },
    { label: "Not assessed", value: indicators.not_assessed },
    { label: "Extraction warnings", value: indicators.extraction_warnings },
  ];
  return (
    <div aria-labelledby="review-indicators-heading" role="region" className="flex flex-col gap-2">
      <div>
        <h3 id="review-indicators-heading" className="text-sm font-semibold">
          Review indicators
        </h3>
        <p className="text-xs text-muted-foreground">
          These counts point to work still to do. They are not a readiness or compliance score.
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {entries.map((entry) => (
          <div key={entry.label} className="rounded-lg border border-border px-3 py-2">
            <dt className="text-xs text-muted-foreground">{entry.label}</dt>
            <dd className="text-lg font-semibold tabular-nums">{entry.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function SelectedEvidenceList({ evidence }: { evidence: SelectedEvidenceOut[] }) {
  if (evidence.length === 0) return null;
  return (
    <details className="rounded-lg border border-border px-4 py-3 text-sm">
      <summary className="cursor-pointer font-medium">
        Company documents compared ({evidence.length})
      </summary>
      <ul className="mt-3 flex flex-col gap-3">
        {evidence.map((item) => (
          <li key={item.document_id} className="flex items-start justify-between gap-3">
            <span className="min-w-0">
              <span className="block break-words font-medium">
                {item.original_filename} (version {item.version})
              </span>
              <span className="block text-xs text-muted-foreground">
                Your label: {evidenceLabelName(item.evidence_label)} · {item.pages_with_text} of{" "}
                {plural(item.page_count, "page")} with readable text
              </span>
              {!item.matches_selected_version ? (
                <span className="mt-1 block text-xs text-amber-900 dark:text-amber-200">
                  This document has changed since it was selected. The matches refer to the version
                  selected for this analysis.
                </span>
              ) : null}
            </span>
            <TextStatusBadge status={item.text_status} />
          </li>
        ))}
      </ul>
    </details>
  );
}

function ExportButtons({ runId }: { runId: string }) {
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download(format: ExportFormat) {
    setBusy(format);
    setError(null);
    try {
      const { blob, filename } = await downloadChecklistExport(runId, format);
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement("a");
      link.href = url;
      link.download = filename;
      window.document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-1">
        <Button
          variant="outline"
          size="sm"
          disabled={busy !== null}
          onClick={() => void download("csv")}
        >
          {busy === "csv" ? "Preparing CSV…" : "Export CSV"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={busy !== null}
          onClick={() => void download("json")}
        >
          {busy === "json" ? "Preparing JSON…" : "Export JSON"}
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-xs text-red-700 dark:text-red-300">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function MatchedDocuments({ item }: { item: ChecklistItemOut }) {
  const { assessment } = item;
  if (!assessment) return <span className="text-muted-foreground">Not assessed</span>;
  const byDocument = new Map<string, { filename: string; counted: number }>();
  for (const source of assessment.sources) {
    const entry = byDocument.get(source.document_id) ?? {
      filename: source.document_filename,
      counted: 0,
    };
    if (source.counts_as_candidate) entry.counted += 1;
    byDocument.set(source.document_id, entry);
  }
  if (byDocument.size === 0) return <span className="text-muted-foreground">None found</span>;
  return (
    <ul className="flex flex-col gap-1">
      {Array.from(byDocument.entries()).map(([id, entry]) => (
        <li key={id} className="break-words">
          {entry.filename}
          {entry.counted === 0 ? (
            <span className="block text-xs text-amber-900 dark:text-amber-200">
              Flagged page only, cannot count as support
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function ChecklistRow({
  number,
  item,
  runId,
  expanded,
  onToggle,
  onSaved,
  onOpenSource,
  onOpenEvidenceSource,
}: {
  number: number;
  item: ChecklistItemOut;
  runId: string;
  expanded: boolean;
  onToggle: () => void;
  onSaved: (saved: DecisionOut) => void;
  onOpenSource: (sourceId: string) => void;
  onOpenEvidenceSource: (sourceId: string) => void;
}) {
  const { requirement, assessment, decision } = item;
  const detailId = `checklist-detail-${requirement.id}`;
  const sources = [...requirement.sources].sort((a, b) => a.page_number - b.page_number);

  return (
    <Fragment>
      <tr className="align-top">
        <td className="max-w-sm px-3 py-3">
          <p className="font-medium">
            <span className="text-muted-foreground">{number}. </span>
            {requirement.title}
          </p>
          <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-muted-foreground">
            {requirement.requirement_text}
          </p>
        </td>
        <td className="px-3 py-3 capitalize">{humanise(requirement.category)}</td>
        <td className="px-3 py-3">
          <StatusBadge status={item.current_status} />
          {assessment &&
          assessment.ai_status === "missing_evidence" &&
          assessment.required_count !== null &&
          assessment.candidate_document_count > 0 ? (
            <p className="mt-1 text-xs text-muted-foreground">
              Candidate evidence in {assessment.candidate_document_count} of{" "}
              {assessment.required_count} documents the tender asks for.
            </p>
          ) : null}
          {item.current_status === "human_reviewed" && assessment ? (
            <p className="mt-1 text-xs text-muted-foreground">
              AI assessment: {checklistStatusLabel(assessment.ai_status)}
            </p>
          ) : null}
        </td>
        <td className="max-w-[14rem] px-3 py-3">
          <MatchedDocuments item={item} />
        </td>
        <td className="max-w-xs px-3 py-3">
          {item.next_action ?? <span className="text-muted-foreground">None proposed</span>}
        </td>
        <td className="px-3 py-3">
          <div className="flex flex-wrap gap-1">
            {sources.map((source) => (
              <Button
                key={source.id}
                variant="outline"
                size="xs"
                aria-label={`View tender source on page ${source.page_number} for ${requirement.title}`}
                onClick={() => onOpenSource(source.id)}
              >
                p. {source.page_number}
              </Button>
            ))}
          </div>
        </td>
        <td className="px-3 py-3">
          <p className="text-xs">
            {decision ? decisionLabel(decision.decision) : DECISION_LABELS.unresolved}
          </p>
          <Button
            variant="outline"
            size="xs"
            className="mt-1"
            aria-expanded={expanded}
            aria-controls={detailId}
            aria-label={`${expanded ? "Hide review for" : "Review"} ${requirement.title}`}
            onClick={onToggle}
          >
            {expanded ? "Hide" : "Review"}
          </Button>
        </td>
      </tr>
      {expanded ? (
        <tr id={detailId}>
          <td colSpan={7} className="bg-muted/20 px-3 py-4">
            <ChecklistDetail
              item={item}
              runId={runId}
              onSaved={onSaved}
              onOpenSource={onOpenSource}
              onOpenEvidenceSource={onOpenEvidenceSource}
            />
          </td>
        </tr>
      ) : null}
    </Fragment>
  );
}

function ChecklistDetail({
  item,
  runId,
  onSaved,
  onOpenSource,
  onOpenEvidenceSource,
}: {
  item: ChecklistItemOut;
  runId: string;
  onSaved: (saved: DecisionOut) => void;
  onOpenSource: (sourceId: string) => void;
  onOpenEvidenceSource: (sourceId: string) => void;
}) {
  const { requirement, assessment, earlier_decision: earlier } = item;
  const tenderSources = [...requirement.sources].sort((a, b) => a.page_number - b.page_number);

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-2">
          <h3 className="text-sm font-semibold">Tender requirement</h3>
          <p className="whitespace-pre-wrap text-sm">{requirement.requirement_text}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted-foreground">Stage</dt>
            <dd className="capitalize">{humanise(requirement.stage)}</dd>
            <dt className="text-muted-foreground">Evidence needed</dt>
            <dd>{requirement.evidence_needed ?? "Not stated"}</dd>
            <dt className="text-muted-foreground">Consequence</dt>
            <dd>{requirement.consequence ?? "Not stated"}</dd>
          </dl>
          {requirement.ambiguity_notes ? (
            <p className="rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">
              Ambiguity: {requirement.ambiguity_notes}
            </p>
          ) : null}
          {tenderSources.map((source) => (
            <figure key={source.id} className="flex flex-col gap-1">
              <blockquote className="whitespace-pre-wrap rounded-md border-l-4 border-primary bg-background px-3 py-2 text-sm">
                {source.quote}
              </blockquote>
              <figcaption>
                <Button
                  variant="link"
                  size="xs"
                  className="px-0"
                  onClick={() => onOpenSource(source.id)}
                >
                  Tender page {source.page_number}
                </Button>
              </figcaption>
            </figure>
          ))}
        </div>

        <div className="flex min-w-0 flex-col gap-2">
          <h3 className="text-sm font-semibold">Candidate evidence</h3>
          {assessment ? (
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium">{assessment.count_summary}</p>
              <p className="whitespace-pre-wrap text-sm">{assessment.explanation}</p>
              {assessment.uncertainty_notes ? (
                <p className="rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">
                  Uncertainty: {assessment.uncertainty_notes}
                </p>
              ) : null}
              {assessment.sources.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No candidate passage was found in the selected documents. This does not show that
                  the evidence does not exist.
                </p>
              ) : (
                assessment.sources.map((source) => (
                  <figure key={source.id} className="flex flex-col gap-1">
                    <figcaption className="text-xs text-muted-foreground">
                      {source.document_filename} · Your label:{" "}
                      {evidenceLabelName(source.evidence_label)} · page {source.page_number}
                    </figcaption>
                    <blockquote className="whitespace-pre-wrap rounded-md border-l-4 border-sky-400 bg-background px-3 py-2 text-sm">
                      {source.quote}
                    </blockquote>
                    {source.relationship ? <p className="text-xs">{source.relationship}</p> : null}
                    {!source.counts_as_candidate ? (
                      <p className="text-xs text-amber-900 dark:text-amber-200">
                        This page was flagged during text extraction, so this passage cannot count
                        as support.
                      </p>
                    ) : null}
                    <Button
                      variant="link"
                      size="xs"
                      className="w-fit px-0"
                      onClick={() => onOpenEvidenceSource(source.id)}
                    >
                      Open evidence page {source.page_number}
                    </Button>
                  </figure>
                ))
              )}
              <p className="text-xs text-muted-foreground">Suggested by {assessment.model}</p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No company evidence was compared with this requirement in this analysis.
            </p>
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Candidate evidence is a suggestion to review. ReadyBid does not check whether a document is
        genuine, signed, current or sufficient for this tender.
      </p>

      {earlier ? (
        <Notice title="Earlier decision (hint only)">
          On an earlier analysis of this tender, a reviewer recorded &ldquo;
          {decisionLabel(earlier.decision)}&rdquo; on {formatDateTime(earlier.created_at)}
          {earlier.notes ? `: ${earlier.notes}` : "."} It does not carry over. Record a decision for
          this analysis if it still applies.
        </Notice>
      ) : null}

      <DecisionForm
        runId={runId}
        requirementId={requirement.id}
        current={item.decision}
        onSaved={onSaved}
      />
      <DecisionHistory history={item.decision_history} />
    </div>
  );
}

function DecisionForm({
  runId,
  requirementId,
  current,
  onSaved,
}: {
  runId: string;
  requirementId: string;
  current: DecisionOut | null;
  onSaved: (saved: DecisionOut) => void;
}) {
  const [decision, setDecision] = useState<Decision>(asDecision(current?.decision));
  const [notes, setNotes] = useState(current?.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const notesRequired = decision === "not_applicable";
  const trimmed = notes.trim();
  const headingId = `decision-heading-${requirementId}`;
  const selectId = `decision-select-${requirementId}`;
  const notesId = `decision-notes-${requirementId}`;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    if (notesRequired && trimmed === "") {
      setError("Add a note explaining why this requirement does not apply.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const out = await api.recordDecision(runId, {
        requirement_id: requirementId,
        decision,
        notes: trimmed === "" ? null : trimmed,
      });
      setSaved(true);
      onSaved(out);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      aria-labelledby={headingId}
      onSubmit={(event) => void submit(event)}
      className="flex flex-col gap-3 rounded-lg border border-border bg-background p-4"
    >
      <h3 id={headingId} className="text-sm font-semibold">
        Your review decision
      </h3>
      <p className="text-xs text-muted-foreground">
        {current
          ? `Current: ${decisionLabel(current.decision)}, recorded ${formatDateTime(current.created_at)} by reviewer ${shortId(current.reviewer_id)}.`
          : "No decision recorded for this analysis yet."}
      </p>
      <div className="flex flex-col gap-1">
        <label htmlFor={selectId} className="text-xs font-medium">
          Decision
        </label>
        <select
          id={selectId}
          value={decision}
          disabled={saving}
          onChange={(event) => {
            setDecision(asDecision(event.target.value));
            setSaved(false);
          }}
          className="h-8 w-full max-w-sm rounded-lg border border-input bg-background px-2 text-sm"
        >
          {DECISIONS.map((value) => (
            <option key={value} value={value}>
              {DECISION_LABELS[value]}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={notesId} className="text-xs font-medium">
          Notes {notesRequired ? "(required for Not applicable)" : "(optional)"}
        </label>
        <textarea
          id={notesId}
          value={notes}
          rows={3}
          maxLength={NOTES_MAX_LENGTH}
          disabled={saving}
          aria-invalid={notesRequired && error !== null && trimmed === ""}
          onChange={(event) => {
            setNotes(event.target.value);
            setSaved(false);
          }}
          className="w-full rounded-lg border border-input bg-background px-2 py-1.5 text-sm"
        />
        <p className="text-xs text-muted-foreground">
          {notes.length} / {NOTES_MAX_LENGTH}
        </p>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {saved ? (
        <p role="status" className="text-xs text-emerald-800 dark:text-emerald-300">
          Decision recorded.
        </p>
      ) : null}
      <Button type="submit" size="sm" className="w-fit" disabled={saving}>
        {saving ? "Saving…" : "Record decision"}
      </Button>
      <p className="text-xs text-muted-foreground">
        Each decision is saved with your account and the time. Earlier decisions stay in the history.
      </p>
    </form>
  );
}

/** `history` arrives oldest first from the API; it is shown newest first. */
function DecisionHistory({ history }: { history: DecisionOut[] }) {
  if (history.length === 0) return null;
  const newestFirst = [...history].reverse();
  return (
    <details className="text-xs">
      <summary className="cursor-pointer text-muted-foreground">
        Decision history ({history.length}, newest first)
      </summary>
      <ol className="mt-2 flex flex-col gap-1">
        {newestFirst.map((entry) => (
          <li key={entry.id} className="break-words">
            {formatDateTime(entry.created_at)} · {decisionLabel(entry.decision)} · reviewer{" "}
            {shortId(entry.reviewer_id)}
            {entry.notes ? ` · ${entry.notes}` : ""}
          </li>
        ))}
      </ol>
    </details>
  );
}
