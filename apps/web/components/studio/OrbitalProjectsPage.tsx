import ProjectsPageBody from "@/components/page-bodies/ProjectsPageBody";
import { OrbitalStudioPageFrame } from "./OrbitalStudioPageFrame";

export function OrbitalProjectsPage() {
  return (
    <OrbitalStudioPageFrame
      eyebrow="Studio / Project operations"
      title="Projects"
      description="Track tasks and milestones with evidence links and explicit completion state."
    >
      <ProjectsPageBody />
    </OrbitalStudioPageFrame>
  );
}
