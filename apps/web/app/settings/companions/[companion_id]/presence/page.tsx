import { OrbitalPresencePage } from "@/components/presence/OrbitalPresencePage";
import { CompanionSettingsScope } from "@/components/settings/CompanionSettingsScope";

export default async function SettingsPresencePage({ params }: { params: Promise<{ companion_id: string }> }) {
  const { companion_id } = await params;
  return <CompanionSettingsScope companionId={companion_id}><OrbitalPresencePage /></CompanionSettingsScope>;
}
