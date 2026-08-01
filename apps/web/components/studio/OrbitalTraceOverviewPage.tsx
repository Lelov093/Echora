import TraceOverviewPageBody from "@/components/page-bodies/TraceOverviewPageBody";
import { OrbitalTracePageFrame } from "./OrbitalTracePageFrame";

export function OrbitalTraceOverviewPage() {
  return (
    <OrbitalTracePageFrame
      eyebrow="Studio / Evidence map"
      title="Trace"
      description="Navigate from system runs to permission evidence, redacted replay, and external-channel audit."
    >
      <TraceOverviewPageBody />
    </OrbitalTracePageFrame>
  );
}
