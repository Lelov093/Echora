import DiscordChannelSettingsPageBody from "@/components/page-bodies/DiscordChannelSettingsPageBody";
import { OrbitalChannelsPageFrame } from "./OrbitalChannelsPageFrame";

export function OrbitalDiscordSettingsPage() {
  return (
    <OrbitalChannelsPageFrame
      eyebrow="Studio / Discord identities"
      title="Discord Setup"
      description="Verify bot readiness and bind each external identity to exactly one Companion without rendering credentials."
    >
      <DiscordChannelSettingsPageBody />
    </OrbitalChannelsPageFrame>
  );
}
