"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, FolderOpen, LayoutDashboard } from "lucide-react";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tenders", label: "Tenders", icon: FileText },
  { href: "/documents", label: "Company documents", icon: FolderOpen },
] as const;

/**
 * Main navigation with the current section highlighted. `usePathname` is request-time data
 * on dynamic routes, so render this inside `<Suspense fallback={<SiteNavFallback />}>`.
 */
export function SiteNav() {
  return <NavLinks pathname={usePathname()} />;
}

/** Same links without an active highlight, shown while the pathname is not yet known. */
export function SiteNavFallback() {
  return <NavLinks pathname={null} />;
}

function NavLinks({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="Main" className="flex flex-wrap items-center gap-1">
      {links.map(({ href, label, icon: Icon }) => {
        const active =
          pathname !== null && (href === "/" ? pathname === "/" : pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
