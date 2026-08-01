import { DiscordSettingsPage } from "@/components/channels/DiscordSettingsPage";
import { SectionNav } from "@/components/navigation/SectionNav";
import { settingsNavItems } from "@/lib/navigation/routes";

export default function DiscordChannelSettingsPageBody() {
  return (
    <>
      <SectionNav title="Settings" eyebrow="Boundary and channel controls" items={settingsNavItems} />
      <DiscordSettingsPage />
    </>
  );
}
