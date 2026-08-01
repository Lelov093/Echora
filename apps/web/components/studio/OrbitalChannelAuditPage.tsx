import ChannelAuditPageBody from "@/components/page-bodies/ChannelAuditPageBody";
import { OrbitalChannelsPageFrame } from "./OrbitalChannelsPageFrame";

export function OrbitalChannelAuditPage() {
  return (
    <OrbitalChannelsPageFrame
      eyebrow="Studio / Channel evidence"
      title="Channel Audit"
      description="Inspect trace, continuity, audit, and revoke evidence for the selected external-channel binding."
    >
      <ChannelAuditPageBody />
    </OrbitalChannelsPageFrame>
  );
}
