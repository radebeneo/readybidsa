"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AuthGate } from "@/components/auth-gate";
import { ErrorBlock, LoadingBlock, Notice } from "@/components/notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api, errorMessage, type Loadable } from "@/lib/api-client";
import type { OrganisationOut, TenderOut } from "@/lib/api-types";
import { formatDateTime } from "@/lib/format";

export function TendersWorkspace() {
  // Keyed by user so switching accounts never shows the previous user's data.
  return <AuthGate>{(session) => <OrganisationTenders key={session.user.id} />}</AuthGate>;
}

function OrganisationTenders() {
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

  function reload() {
    setOrganisations({ state: "loading" });
    setReloadKey((key) => key + 1);
  }

  if (organisations.state === "loading") return <LoadingBlock label="Loading your organisation" />;
  if (organisations.state === "error") {
    return <ErrorBlock message={organisations.message} onRetry={reload} />;
  }

  // The API allows one organisation per user in this slice.
  const organisation = organisations.data[0];
  if (!organisation) {
    return (
      <CreateOrganisationForm
        onCreated={(created) => setOrganisations({ state: "ready", data: [created] })}
        onConflict={reload}
      />
    );
  }
  return <TenderList organisation={organisation} />;
}

function CreateOrganisationForm({
  onCreated,
  onConflict,
}: {
  onCreated: (organisation: OrganisationOut) => void;
  onConflict: () => void;
}) {
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Enter your organisation's name.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      onCreated(await api.createOrganisation(trimmed));
    } catch (caught) {
      // 409: this account already belongs to an organisation, so load it instead.
      if (caught instanceof ApiError && caught.status === 409) {
        onConflict();
        return;
      }
      setError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <section
      aria-labelledby="create-organisation-heading"
      className="max-w-lg rounded-xl border border-border bg-background p-5"
    >
      <h2 id="create-organisation-heading" className="text-base font-semibold">
        Set up your organisation
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Tenders and documents belong to an organisation. Only its members can see them.
      </p>
      <form onSubmit={(event) => void handleSubmit(event)} className="mt-4 flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="organisation-name" className="text-sm font-medium">
            Organisation name
          </label>
          <Input
            id="organisation-name"
            required
            maxLength={200}
            autoComplete="organization"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Button type="submit" size="lg" disabled={pending}>
          {pending ? "Creating…" : "Create organisation"}
        </Button>
      </form>
    </section>
  );
}

function TenderList({ organisation }: { organisation: OrganisationOut }) {
  const router = useRouter();
  const [tenders, setTenders] = useState<Loadable<TenderOut[]>>({ state: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [title, setTitle] = useState("");
  const [reference, setReference] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.listTenders(organisation.id).then(
      (data) => {
        if (!cancelled) setTenders({ state: "ready", data });
      },
      (caught: unknown) => {
        if (!cancelled) setTenders({ state: "error", message: errorMessage(caught) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [organisation.id, reloadKey]);

  function reload() {
    setTenders({ state: "loading" });
    setReloadKey((key) => key + 1);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedTitle = title.trim();
    const trimmedReference = reference.trim();
    if (!trimmedTitle) {
      setError("Enter a tender title.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const tender = await api.createTender(organisation.id, {
        title: trimmedTitle,
        reference: trimmedReference === "" ? null : trimmedReference,
      });
      // Stay in the pending state while the detail page loads.
      router.push(`/tenders/${encodeURIComponent(tender.id)}`);
    } catch (caught) {
      setError(errorMessage(caught));
      setPending(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <section
        aria-labelledby="tender-list-heading"
        className="flex flex-col gap-4 rounded-xl border border-border bg-background p-5"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="tender-list-heading" className="text-base font-semibold">
            Tender workspaces
          </h2>
          <span className="text-xs text-muted-foreground">{organisation.name}</span>
        </div>

        {tenders.state === "loading" ? <LoadingBlock label="Loading tenders" /> : null}
        {tenders.state === "error" ? <ErrorBlock message={tenders.message} onRetry={reload} /> : null}
        {tenders.state === "ready" && tenders.data.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-8 text-center">
            <p className="text-sm font-medium">No tenders yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Create a tender workspace to upload its PDF.
            </p>
          </div>
        ) : null}
        {tenders.state === "ready" && tenders.data.length > 0 ? (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {tenders.data.map((tender) => (
              <li key={tender.id}>
                <Link
                  href={`/tenders/${encodeURIComponent(tender.id)}`}
                  className="flex flex-col gap-0.5 px-4 py-3 transition-colors hover:bg-muted/50"
                >
                  <span className="text-sm font-medium">{tender.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {tender.reference ? `${tender.reference} · ` : ""}
                    Created {formatDateTime(tender.created_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section
        aria-labelledby="create-tender-heading"
        className="h-fit rounded-xl border border-border bg-background p-5"
      >
        <h2 id="create-tender-heading" className="text-base font-semibold">
          New tender
        </h2>
        <form onSubmit={(event) => void handleCreate(event)} className="mt-4 flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="tender-title" className="text-sm font-medium">
              Title
            </label>
            <Input
              id="tender-title"
              required
              maxLength={300}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="tender-reference" className="text-sm font-medium">
              Reference <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <Input
              id="tender-reference"
              maxLength={200}
              placeholder="e.g. RFQ 2026/014"
              value={reference}
              onChange={(event) => setReference(event.target.value)}
            />
          </div>
          {error ? <Notice tone="error">{error}</Notice> : null}
          <Button type="submit" disabled={pending}>
            {pending ? "Creating…" : "Create tender"}
          </Button>
        </form>
      </section>
    </div>
  );
}
