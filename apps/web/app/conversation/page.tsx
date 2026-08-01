import { ConversationEntry } from "@/features/conversation/ConversationEntry";

export default async function ConversationPage({ searchParams }: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  return <ConversationEntry
    requestedCompanionId={first(params.companion_id)}
    requestedConversationId={first(params.conversation_id) ?? first(params.conversation)}
  />;
}

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}
