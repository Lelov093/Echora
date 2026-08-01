import ChannelSettingsPageBody from "@/components/page-bodies/ChannelSettingsPageBody";
import { OrbitalChannelsPageFrame } from "./OrbitalChannelsPageFrame";

export function OrbitalChannelSettingsPage() {
  return (
    <OrbitalChannelsPageFrame
      eyebrow="Studio / External channels"
      title="Channel Gateway"
      description="Inspect providers, Companion bindings, delivery policy, review queues, and revocable external-channel state."
    >
      <ChannelSettingsPageBody />
    </OrbitalChannelsPageFrame>
  );
}
