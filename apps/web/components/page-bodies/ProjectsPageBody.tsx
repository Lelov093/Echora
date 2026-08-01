import { SectionNav } from "@/components/navigation/SectionNav";
import { ProjectWorkspace } from "@/components/project/ProjectWorkspace";
import { agentLabNavItems } from "@/lib/navigation/routes";

export default function ProjectsPageBody() {
  return (
    <>
      <SectionNav title="Agent Lab" eyebrow="Projects, tools, evaluation" items={agentLabNavItems} />
      <ProjectWorkspace />
    </>
  );
}
