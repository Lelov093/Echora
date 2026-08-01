import { CompanionAffectSettings } from "@/features/affect/CompanionAffectSettings";

export default async function SettingsAffectPage({ params }: { params: Promise<{ companion_id: string }> }) {
  const { companion_id } = await params;
  return <CompanionAffectSettings companionId={companion_id} />;
}
