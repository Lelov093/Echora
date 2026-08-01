import { redirect } from "next/navigation";

export default async function ProfilePage({ params }: { params: Promise<{ companion_id: string }> }) {
  const { companion_id } = await params;
  redirect(`/settings/companions/${companion_id}/profile`);
}
