import { redirect } from "next/navigation";

export default async function PresencePage({ searchParams }: { searchParams: Promise<{ companion_id?: string }> }) {
  const { companion_id } = await searchParams;
  redirect(companion_id ? `/settings/companions/${companion_id}/presence` : "/settings");
}
