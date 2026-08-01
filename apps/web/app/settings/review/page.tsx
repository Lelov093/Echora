import { Suspense } from "react";
import { ReviewInbox } from "@/features/review-inbox/ReviewInbox";

export default function SettingsReviewPage() {
  return <Suspense fallback={null}><ReviewInbox /></Suspense>;
}
