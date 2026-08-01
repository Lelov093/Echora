import { CompanionProfile } from "@/features/profile/CompanionProfile";

export default async function SettingsProfilePage({ params }: { params: Promise<{ companion_id: string }> }) {
  const { companion_id } = await params;
  return <CompanionProfile companionId={companion_id} />;
}
