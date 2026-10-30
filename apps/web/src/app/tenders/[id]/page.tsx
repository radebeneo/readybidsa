import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingBlock } from "@/components/notice";
import { TenderDetail } from "@/components/tender-detail";

export const metadata: Metadata = { title: "Tender" };

// TenderDetail reads the route id with useParams, which suspends during prerendering
// under cacheComponents, so it needs a Suspense boundary.
export default function TenderPage() {
  return (
    <Suspense fallback={<LoadingBlock label="Loading tender" />}>
      <TenderDetail />
    </Suspense>
  );
}
