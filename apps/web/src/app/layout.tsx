import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { AccountStatus } from "@/components/account-status";
import { Suspense } from "react";
import { SiteNav, SiteNavFallback } from "@/components/site-nav";
import "./globals.css";

// `--font-sans` matches the variable consumed by `@theme inline` in globals.css.
const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "ReadyBid SA",
    template: "%s | ReadyBid SA",
  },
  description:
    "Tender-readiness assistant: extract tender requirements, match company evidence and flag gaps for human review.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-muted/30">
        <header className="border-b border-border bg-background">
          <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
            <Link href="/" className="flex items-center gap-2">
              <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
                RB
              </span>
              <span className="text-base font-semibold tracking-tight">ReadyBid SA</span>
            </Link>
            <div className="flex flex-wrap items-center gap-4">
              <Suspense fallback={<SiteNavFallback />}>
                <SiteNav />
              </Suspense>
              <AccountStatus />
            </div>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-8">
          {children}
        </main>

        <footer className="border-t border-border bg-background">
          <p className="mx-auto w-full max-w-6xl px-6 py-4 text-xs text-muted-foreground">
            ReadyBid SA assists with tender preparation only. It does not provide legal certification,
            guarantee eligibility or predict awards. Always verify requirements against the official
            tender documents.
          </p>
        </footer>
      </body>
    </html>
  );
}
