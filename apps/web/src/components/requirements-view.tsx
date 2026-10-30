"use client";

import { Notice } from "@/components/notice";
import { Button } from "@/components/ui/button";
import type { CoverageOut, RequirementOut, RequirementsOut } from "@/lib/api-types";
import { extractionLabel, humanise, plural } from "@/lib/format";

export function RequirementsView({
  data,
  onOpenSource,
}: {
  data: RequirementsOut;
  onOpenSource: (sourceId: string) => void;
}) {
  const { analysis, coverage, document } = data;
  const requirements = [...data.requirements].sort((a, b) => a.position - b.position);

  return (
    <section
      aria-labelledby="requirements-heading"
      className="flex flex-col gap-4 rounded-xl border border-border bg-background p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="requirements-heading" className="text-base font-semibold">
          Extracted requirements
        </h2>
        <span className="text-xs text-muted-foreground">
          {document.original_filename} · version {document.version} · {analysis.model}
        </span>
      </div>

      {data.notice ? <Notice>{data.notice}</Notice> : null}
      <CoverageSummary coverage={coverage} />

      {requirements.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-8 text-center">
          <p className="text-sm font-medium">No verified requirements</p>
          <p className="mt-1 text-sm text-muted-foreground">
            No requirement could be matched to a quoted passage in the document. Review the
            tender PDF directly.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[56rem] text-left text-sm">
            <caption className="sr-only">
              Requirements extracted from {document.original_filename}
            </caption>
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">
                  #
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Requirement
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Category
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Stage
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Evidence needed
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Consequence
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Sources
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {requirements.map((requirement, index) => (
                <RequirementRow
                  key={requirement.id}
                  number={index + 1}
                  requirement={requirement}
                  onOpenSource={onOpenSource}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function RequirementRow({
  number,
  requirement,
  onOpenSource,
}: {
  number: number;
  requirement: RequirementOut;
  onOpenSource: (sourceId: string) => void;
}) {
  const sources = [...requirement.sources].sort((a, b) => a.page_number - b.page_number);
  return (
    <tr className="align-top">
      <td className="px-3 py-3 text-muted-foreground">{number}</td>
      <td className="max-w-md px-3 py-3">
        <p className="font-medium">{requirement.title}</p>
        <p className="mt-1 whitespace-pre-wrap text-muted-foreground">
          {requirement.requirement_text}
        </p>
        {requirement.ambiguity_notes ? (
          <p className="mt-2 rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">
            Ambiguity: {requirement.ambiguity_notes}
          </p>
        ) : null}
      </td>
      <td className="px-3 py-3 capitalize">{humanise(requirement.category)}</td>
      <td className="px-3 py-3 capitalize">{humanise(requirement.stage)}</td>
      <td className="px-3 py-3">
        {requirement.evidence_needed ?? <span className="text-muted-foreground">Not stated</span>}
      </td>
      <td className="px-3 py-3">
        {requirement.consequence ?? <span className="text-muted-foreground">Not stated</span>}
      </td>
      <td className="px-3 py-3">
        <div className="flex flex-wrap gap-1">
          {sources.map((source) => (
            <Button
              key={source.id}
              variant="outline"
              size="xs"
              aria-label={`View source on page ${source.page_number} for ${requirement.title}`}
              onClick={() => onOpenSource(source.id)}
            >
              p. {source.page_number}
            </Button>
          ))}
        </div>
      </td>
    </tr>
  );
}

export function CoverageSummary({ coverage }: { coverage: CoverageOut }) {
  const pages = coverage.pages_total;
  const hasGaps =
    coverage.complete === false ||
    coverage.flagged_pages.length > 0 ||
    coverage.truncated_pages.length > 0 ||
    coverage.groups_failed > 0;
  const removedOutput = coverage.rejected_citations > 0 || coverage.dropped_requirements > 0;
  const truncated = coverage.truncated_pages;

  return (
    <div className="flex flex-col gap-3">
      {hasGaps ? (
        <Notice tone="warn" title="Coverage incomplete">
          <p>
            Part of the tender was not fully read. Requirements on these pages may be missing, so
            check them in the PDF yourself.
          </p>
          <ul className="mt-2 list-disc pl-5">
            {coverage.flagged_pages.map((warning) => (
              <li key={`flagged-${warning.page_number}`}>
                Page {warning.page_number}: {extractionLabel(warning.status)}
                {warning.note ? ` (${warning.note})` : ""}
              </li>
            ))}
            {truncated.length > 0 ? (
              <li>
                Only part of the text on {truncated.length === 1 ? "page" : "pages"}{" "}
                {truncated.join(", ")} was analysed.
              </li>
            ) : null}
            {coverage.groups_failed > 0 ? (
              <li>
                {coverage.groups_failed} of {plural(coverage.groups_total, "page group")} could not
                be analysed.
              </li>
            ) : null}
          </ul>
        </Notice>
      ) : coverage.complete === true ? (
        <Notice tone="success">
          {pages !== null
            ? `All ${pages} ${pages === 1 ? "page was" : "pages were"} read and analysed.`
            : "All pages were read and analysed."}
        </Notice>
      ) : null}

      {removedOutput ? (
        <Notice title="Unverified output removed">
          {coverage.rejected_citations > 0 ? (
            <p>
              {plural(coverage.rejected_citations, "citation")} rejected because the quoted text
              was not found on the cited page.
            </p>
          ) : null}
          {coverage.dropped_requirements > 0 ? (
            <p>
              {plural(coverage.dropped_requirements, "requirement")} removed because none of the
              citations could be verified.
            </p>
          ) : null}
        </Notice>
      ) : null}
    </div>
  );
}
