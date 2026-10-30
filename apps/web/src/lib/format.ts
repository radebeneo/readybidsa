const dateTimeFormat = new Intl.DateTimeFormat("en-ZA", { dateStyle: "medium", timeStyle: "short" });

export function formatDateTime(value: string | null): string {
  if (!value) return "Unknown date";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateTimeFormat.format(date);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

const EXTRACTION_LABELS: Record<string, string> = {
  ok: "text read",
  suspicious: "little readable text (possibly scanned)",
  empty: "no extractable text",
  error: "could not be read",
};

/** Plain-language label for a page's text-extraction status. */
export function extractionLabel(status: string): string {
  return EXTRACTION_LABELS[status] ?? humanise(status);
}

/** 120 -> "2 minutes", 45 -> "45 seconds". */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return plural(Math.max(Math.round(seconds), 0), "second");
  return plural(Math.round(seconds / 60), "minute");
}

/** "image_only" -> "image only". Used for model and extraction labels. */
export function humanise(value: string): string {
  return value.replace(/[_-]+/g, " ").trim();
}
