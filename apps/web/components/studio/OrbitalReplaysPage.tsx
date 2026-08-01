import ReplaysPageBody from "@/components/page-bodies/ReplaysPageBody";
import { OrbitalTracePageFrame } from "./OrbitalTracePageFrame";

export function OrbitalReplaysPage() {
  return (
    <OrbitalTracePageFrame
      eyebrow="Studio / Run snapshots"
      title="Replay Center"
      description="Inspect stored run snapshots, annotate evidence, and promote reviewed failures into bad cases or regressions."
    >
      <ReplaysPageBody />
    </OrbitalTracePageFrame>
  );
}
