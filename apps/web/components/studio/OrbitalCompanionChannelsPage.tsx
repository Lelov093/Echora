"use client";

import { useParams } from "next/navigation";
import { ChannelGatewayWorkspace } from "@/components/channels/ChannelGatewayWorkspace";
import { OrbitalChannelsPageFrame } from "./OrbitalChannelsPageFrame";

export function OrbitalCompanionChannelsPage() {
  const params = useParams<{ companion_id: string }>();
  const companionId = typeof params?.companion_id === "string" ? params.companion_id : null;
  return (
    <OrbitalChannelsPageFrame
      eyebrow="Studio / Companion binding"
      title="Companion Channel Binding"
      description="Inspect external-channel policy and evidence for one explicit Companion scope."
      scope={companionId ? `Companion ${companionId.slice(0, 8)}` : "Companion scope unavailable"}
    >
      <ChannelGatewayWorkspace view="companion" companionId={companionId} />
    </OrbitalChannelsPageFrame>
  );
}
