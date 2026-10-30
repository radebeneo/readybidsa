"use client";

import Link from "next/link";
import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { TextStatusBadge } from "@/components/evidence-library";
import { ErrorBlock, LoadingBlock, Notice } from "@/components/notice";
import { api, errorMessage, type Loadable } from "@/lib/api-client";
import {
  evidenceLabelName,
  type EvidenceDocumentOut,
  type EvidenceListOut,
} from "@/lib/api-types";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Unreadable files have no text to match, so they can never count as support. */
export function isSelectableEvidence(document: EvidenceDocumentOut): boolean {
  return document.text_status !== "unreadable";
}

/**
 * Explicit choice of the company documents the next analysis compares against the tender.
 * Nothing is selected by default: an empty selection means requirements are extracted only.
 */
export function EvidenceSelector({
  organisationId,
  selected,
  onChange,
  disabled,
}: {
  organisationId: string;
  selected: string[];
  onChange: Dispatch<SetStateAction<string[]>>;
  disabled: boolean;
}) {
  const [evidence, setEvidence] = useState<Loadable<EvidenceListOut>>({ state: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.listEvidence(organisationId).then(
      (data) => {
        if (cancelled) return;
        setEvidence({ state: "ready", data });
        // Drop selections that no longer exist or cannot be matched.
        const allowed = new Set(data.documents.filter(isSelectableEvidence).map((d) => d.id));
        onChange((current) => {
          const kept = current.filter((id) => allowed.has(id)).slice(0, data.max_per_analysis);
          return kept.length === current.length ? current : kept;
        });
      },
      (error: unknown) => {
        if (!cancelled) setEvidence({ state: "error", message: errorMessage(error) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [organisationId, reloadKey, onChange]);

  function reload() {
    setEvidence({ state: "loading" });
    setReloadKey((key) => key + 1);
  }

  const max = evidence.state === "ready" ? evidence.data.max_per_analysis : 0;
  const atCap = evidence.state === "ready" && selected.length >= max;

  function toggle(id: string, checked: boolean) {
    onChange((current) => {
      if (!checked) return current.filter((value) => value !== id);
      if (current.includes(id) || current.length >= max) return current;
      return [...current, id];
    });
  }

  return (
    <section
      aria-labelledby="evidence-select-heading"
      className="flex flex-col gap-4 rounded-xl border border-border bg-background p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="evidence-select-heading" className="text-base font-semibold">
          Company evidence for the next analysis
        </h2>
        {evidence.state === "ready" && evidence.data.documents.length > 0 ? (
          <span className="text-xs text-muted-foreground" aria-live="polite">
            {selected.length} of up to {max} selected
          </span>
        ) : null}
      </div>
      <p className="text-sm text-muted-foreground">
        Choose which company documents ReadyBid compares with the tender requirements. Only the
        documents you tick are used. With none ticked, the analysis extracts requirements only.
      </p>

      {evidence.state === "loading" ? <LoadingBlock label="Loading company documents" /> : null}
      {evidence.state === "error" ? (
        <ErrorBlock
          title="Could not load company documents"
          message={evidence.message}
          onRetry={reload}
        />
      ) : null}
      {evidence.state === "ready" && evidence.data.documents.length === 0 ? (
        <Notice>
          No company documents yet.{" "}
          <Link href="/documents" className="font-medium underline underline-offset-4">
            Upload them on the Company documents page
          </Link>{" "}
          to match them against this tender.
        </Notice>
      ) : null}
      {evidence.state === "ready" && evidence.data.documents.length > 0 ? (
        <>
          <ul className="divide-y divide-border rounded-lg border border-border">
            {evidence.data.documents.map((document) => {
              const selectable = isSelectableEvidence(document);
              const checked = selected.includes(document.id);
              const blocked = disabled || !selectable || (!checked && atCap);
              const inputId = `evidence-option-${document.id}`;
              return (
                <li key={document.id}>
                  <label
                    htmlFor={inputId}
                    className={cn(
                      "flex items-start gap-3 px-4 py-3",
                      blocked && !checked ? "opacity-60" : "cursor-pointer hover:bg-muted/40",
                    )}
                  >
                    <input
                      id={inputId}
                      type="checkbox"
                      className="mt-0.5 size-4 shrink-0 accent-primary"
                      checked={checked}
                      disabled={blocked}
                      onChange={(event) => toggle(document.id, event.target.checked)}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block break-words text-sm font-medium">
                        {document.original_filename}
                      </span>
                      <span className="block text-xs text-muted-foreground">
                        Your label: {evidenceLabelName(document.evidence_label)} ·{" "}
                        {document.pages_with_text} of {plural(document.page_count, "page")} with
                        readable text
                      </span>
                      {!selectable ? (
                        <span className="mt-1 block text-xs text-red-700 dark:text-red-300">
                          No readable text, so this document cannot be matched or count as support.
                        </span>
                      ) : null}
                      {document.text_status === "partly_readable" ? (
                        <span className="mt-1 block text-xs text-amber-900 dark:text-amber-200">
                          Only pages with readable text can be matched.
                        </span>
                      ) : null}
                    </span>
                    <TextStatusBadge status={document.text_status} />
                  </label>
                </li>
              );
            })}
          </ul>
          {atCap ? (
            <p className="text-xs text-muted-foreground">
              You have selected the maximum of {max} documents for one analysis.
            </p>
          ) : null}
          {selected.length > 0 ? (
            <button
              type="button"
              disabled={disabled}
              onClick={() => onChange([])}
              className="w-fit text-xs font-medium text-muted-foreground underline underline-offset-4 hover:text-foreground disabled:opacity-50"
            >
              Clear selection
            </button>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
