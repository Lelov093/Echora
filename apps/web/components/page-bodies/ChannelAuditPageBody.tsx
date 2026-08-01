import { ChannelGatewayWorkspace } from "@/components/channels/ChannelGatewayWorkspace";
import { SectionNav } from "@/components/navigation/SectionNav";
import { traceNavItems } from "@/lib/navigation/routes";

export default function ChannelAuditPageBody() {
  return (
    <>
      <SectionNav title="Trace" eyebrow="Evidence and replay" items={traceNavItems} />
      <ChannelGatewayWorkspace view="audit" />
    </>
  );
}
