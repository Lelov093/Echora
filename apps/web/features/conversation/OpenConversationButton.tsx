"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowRight, MessageCircle } from "lucide-react";
import { createConversation } from "@/lib/api/conversations";

export function OpenConversationButton({ companionId, userId, mode, conversationId }: { companionId: string; userId?: string; mode: string; conversationId?: string | null }) {
  const router = useRouter();
  const create = useMutation({
    mutationFn: () => createConversation({ user_id: userId, companion_id: companionId, title: "新的对话", mode_key: mode }),
    onSuccess: (conversation) => router.push(`/companions/${companionId}/conversations/${conversation.id}`),
  });

  return <button className="companion-primary-action" disabled={create.isPending} onClick={() => conversationId ? router.push(`/companions/${companionId}/conversations/${conversationId}`) : create.mutate()}><MessageCircle size={18} />{create.isPending ? "正在准备对话" : "继续对话"}<ArrowRight size={18} /></button>;
}
