"use client";

import { useParams } from "next/navigation";
import { ChannelGatewayWorkspace } from "@/components/channels/ChannelGatewayWorkspace";

export default function CompanionChannelsPageBody() {
  const params = useParams<{ companion_id: string }>();
  const companionId = typeof params?.companion_id === "string" ? params.companion_id : null;
  return <ChannelGatewayWorkspace view="companion" companionId={companionId} />;
}
