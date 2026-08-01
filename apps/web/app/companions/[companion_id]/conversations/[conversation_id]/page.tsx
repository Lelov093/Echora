import { ConversationWorkspace } from "@/features/conversation/ConversationWorkspace";

export default async function ConversationPage({ params }: { params: Promise<{ companion_id: string; conversation_id: string }> }) {
  const { companion_id, conversation_id } = await params;
  return <ConversationWorkspace companionId={companion_id} conversationId={conversation_id} />;
}
