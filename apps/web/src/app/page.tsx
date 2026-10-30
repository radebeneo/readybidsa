import { Suspense } from "react";
import { ApiStatusPanel, ApiStatusPanelSkeleton } from "@/components/api-status-panel";

const workflow = [
  { step: "1", title: "Upload tender", body: "Add a text-readable tender PDF. Image-only pages are flagged, never skipped." },
  { step: "2", title: "Extract requirements", body: "Requirements are extracted with their source passages so you can check them." },
  { step: "3", title: "Match evidence", body: "Company documents are matched to each requirement and gaps are flagged." },
  { step: "4", title: "Review", body: "You accept, reject or edit each match. Decisions are recorded." },
];

export default function DashboardPage() {
  return (
    <>
      <section>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Prepare tender submissions by checking requirements against your company evidence.
        </p>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-xl border border-border bg-background p-5 lg:col-span-2">
          <h2 className="text-base font-semibold">How ReadyBid works</h2>
          <ol className="mt-4 grid gap-4 sm:grid-cols-2">
            {workflow.map((item) => (
              <li key={item.step} className="flex gap-3">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">
                  {item.step}
                </span>
                <div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-sm text-muted-foreground">{item.body}</p>
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-5 rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
            These steps are not built yet. This version only connects the dashboard to the API.
          </p>
        </section>

        <section className="rounded-xl border border-border bg-background p-5">
          <h2 className="text-base font-semibold">Service status</h2>
          <p className="mt-1 text-xs text-muted-foreground">Checked live on each visit.</p>
          <div className="mt-2">
            <Suspense fallback={<ApiStatusPanelSkeleton />}>
              <ApiStatusPanel />
            </Suspense>
          </div>
        </section>
      </div>
    </>
  );
}
