import ToolsPageBody from "@/components/page-bodies/ToolsPageBody";
import { OrbitalStudioPageFrame } from "./OrbitalStudioPageFrame";

export function OrbitalToolsPage() {
  return (
    <OrbitalStudioPageFrame
      eyebrow="Studio / Controlled execution"
      title="Tools"
      description="Inspect definitions, risk, permission requirements, run state, and execution impact before confirmation."
      policy="Permission confirmation"
    >
      <ToolsPageBody />
    </OrbitalStudioPageFrame>
  );
}
