/** Determinate progress bar. `value` is a percentage from 0 to 100. */
export function ProgressBar({ value, label }: { value: number; label: string }) {
  const percent = Math.round(Math.min(Math.max(value, 0), 100));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      className="h-2 w-full overflow-hidden rounded-full bg-muted"
    >
      {/* Width is a runtime value, so it is set inline. */}
      <div
        className="h-full rounded-full bg-primary transition-[width] duration-300"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
