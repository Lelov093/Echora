import { SectionNav } from "@/components/navigation/SectionNav";
import { ReplayCenter } from "@/components/replay/ReplayCenter";
import { agentLabNavItems } from "@/lib/navigation/routes";

export default function ReplaysPageBody() {
  return (
    <>
      <SectionNav title="Agent Lab" eyebrow="Projects, tools, evaluation" items={agentLabNavItems} />
      <ReplayCenter />
    </>
  );
}
