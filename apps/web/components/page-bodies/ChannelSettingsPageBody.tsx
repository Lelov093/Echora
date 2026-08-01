import { ChannelGatewayWorkspace } from "@/components/channels/ChannelGatewayWorkspace";
import { SectionNav } from "@/components/navigation/SectionNav";
import { settingsNavItems } from "@/lib/navigation/routes";

export default function ChannelSettingsPageBody() {
  return (
    <>
      <SectionNav title="Settings" eyebrow="Boundary and channel controls" items={settingsNavItems} />
      <ChannelGatewayWorkspace view="overview" />
    </>
  );
}
