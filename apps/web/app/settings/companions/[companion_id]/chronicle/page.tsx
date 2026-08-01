import { LivingChronicle } from "@/features/chronicle/LivingChronicle";

export default async function SettingsChroniclePage({ params }: { params: Promise<{ companion_id: string }> }) {
  const { companion_id } = await params;
  return <LivingChronicle companionId={companion_id} />;
}
