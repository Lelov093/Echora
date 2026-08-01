import BadCasesPageBody from "@/components/page-bodies/BadCasesPageBody";
import { OrbitalStudioPageFrame } from "./OrbitalStudioPageFrame";

export function OrbitalBadCasesPage() {
  return (
    <OrbitalStudioPageFrame
      eyebrow="Studio / Regression inbox"
      title="Bad Cases"
      description="Triage quality failures and promote reviewed evidence into deterministic regression cases."
      scope="All Companions"
      policy="Manual triage required"
    >
      <BadCasesPageBody />
    </OrbitalStudioPageFrame>
  );
}
