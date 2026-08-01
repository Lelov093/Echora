import EvaluationPageBody from "@/components/page-bodies/EvaluationPageBody";
import { OrbitalStudioPageFrame } from "./OrbitalStudioPageFrame";

export function OrbitalEvaluationPage() {
  return (
    <OrbitalStudioPageFrame
      eyebrow="Studio / Quality system"
      title="Evaluation"
      description="Compare datasets, evaluation runs, and regression cases without activating learned behavior."
      scope="All Companions"
      policy="Learned policy: shadow only"
    >
      <div className="orbital-advanced-shadow-banner">
        Learned reranking and bandit policies remain in shadow mode. This surface exposes evidence, not an activation control.
      </div>
      <EvaluationPageBody />
    </OrbitalStudioPageFrame>
  );
}
