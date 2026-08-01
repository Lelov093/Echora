import { MemoryGovernance } from "@/features/memory-governance/MemoryGovernance";

export default async function SettingsMemoryPage({ params }: { params: Promise<{ companion_id: string }> }) {
  const { companion_id } = await params;
  return <MemoryGovernance scopedCompanionId={companion_id} />;
}
