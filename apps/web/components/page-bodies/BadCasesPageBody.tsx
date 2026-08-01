import { BadCaseInboxPanel } from "@/components/bad-cases/BadCaseInboxPanel";
import { SectionNav } from "@/components/navigation/SectionNav";
import { agentLabNavItems } from "@/lib/navigation/routes";

export default function BadCasesPageBody() {
  return (
    <>
      <SectionNav title="Agent Lab" eyebrow="Projects, tools, evaluation" items={agentLabNavItems} />
      <BadCaseInboxPanel />
    </>
  );
}
