import { EvaluationLab } from "@/components/evaluation/EvaluationLab";
import { SectionNav } from "@/components/navigation/SectionNav";
import { agentLabNavItems } from "@/lib/navigation/routes";

export default function EvaluationPageBody() {
  return (
    <>
      <SectionNav title="Agent Lab" eyebrow="Projects, tools, evaluation" items={agentLabNavItems} />
      <EvaluationLab />
    </>
  );
}
