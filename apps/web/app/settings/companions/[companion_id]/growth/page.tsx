import { OrbitalGrowthPage } from "@/components/memory/OrbitalGrowthPage";
import { CompanionSettingsScope } from "@/components/settings/CompanionSettingsScope";

export default async function SettingsGrowthPage({ params }: { params: Promise<{ companion_id: string }> }) {
  const { companion_id } = await params;
  return <CompanionSettingsScope companionId={companion_id}><OrbitalGrowthPage /></CompanionSettingsScope>;
}
