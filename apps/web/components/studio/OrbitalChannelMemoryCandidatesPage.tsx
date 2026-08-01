import ChannelMemoryCandidatesPageBody from "@/components/page-bodies/ChannelMemoryCandidatesPageBody";
import { OrbitalChannelsPageFrame } from "./OrbitalChannelsPageFrame";

export function OrbitalChannelMemoryCandidatesPage() {
  return (
    <OrbitalChannelsPageFrame
      eyebrow="Studio / External memory gate"
      title="Channel Memory Review"
      description="Approve, reject, or redact external-channel memory candidates before any long-term write."
    >
      <ChannelMemoryCandidatesPageBody />
    </OrbitalChannelsPageFrame>
  );
}
