import { redirect } from "next/navigation";

export default async function CompanionRoomPage({ params }: { params: Promise<{ companion_id: string }> }) {
  const { companion_id: companionId } = await params;
  redirect(`/?mode=single&companion_id=${encodeURIComponent(companionId)}`);
}
