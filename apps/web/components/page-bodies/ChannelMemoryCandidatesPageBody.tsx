import { ChannelGatewayWorkspace } from "@/components/channels/ChannelGatewayWorkspace";
import { SectionNav } from "@/components/navigation/SectionNav";
import { memoryNavItems } from "@/lib/navigation/routes";

export default function ChannelMemoryCandidatesPageBody() {
  return (
    <>
      <SectionNav title="Memory" eyebrow="Private and shared review gates" items={memoryNavItems} />
      <ChannelGatewayWorkspace view="memory" />
    </>
  );
}
