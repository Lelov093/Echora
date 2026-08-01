"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { DataState } from "@/components/patterns/DataState";
import { getConversation, listConversations } from "@/lib/api/conversations";
import { useCompanionRosterQuery } from "@/lib/queries/companions";
import { useUIStore } from "@/lib/stores/appStore";

export function ConversationEntry({ requestedCompanionId, requestedConversationId }: {
  requestedCompanionId?: string;
  requestedConversationId?: string;
}) {
  const router = useRouter();
  const roster = useCompanionRosterQuery("product");
  const activeCompanionId = useUIStore((state) => state.activeCompanionId);
  const setActiveCompanionId = useUIStore((state) => state.setActiveCompanionId);
  const companions = roster.data?.items ?? [];
  const requestedCompanion = requestedCompanionId ? companions.find((item) => item.id === requestedCompanionId) : undefined;
  const companion = requestedCompanion ?? companions.find((item) => item.id === activeCompanionId) ?? companions[0];
  const companionId = companion?.id;
  const scopeMismatch = Boolean(requestedCompanionId && roster.isSuccess && !requestedCompanion);
  const requestedConversation = useQuery({
    queryKey: ["conversations", companionId, requestedConversationId, "entry"],
    queryFn: () => getConversation(requestedConversationId ?? "", companionId ?? ""),
    enabled: Boolean(companionId && requestedConversationId) && !scopeMismatch,
  });
  const recentConversations = useQuery({
    queryKey: ["conversations", companionId, "entry"],
    queryFn: () => listConversations({ companion_id: companionId, status: "active", page_size: 1 }),
    enabled: Boolean(companionId) && !requestedConversationId && !scopeMismatch,
  });
  const destination = requestedConversation.data?.id
    ? `/companions/${companionId}/conversations/${requestedConversation.data.id}`
    : !requestedConversationId && recentConversations.data?.items[0]
      ? `/companions/${companionId}/conversations/${recentConversations.data.items[0].id}`
      : !requestedConversationId && recentConversations.isSuccess && companion
        ? `/?mode=single&companion_id=${encodeURIComponent(companion.id)}`
        : null;

  useEffect(() => {
    if (!destination || !companionId) return;
    setActiveCompanionId(companionId);
    router.replace(destination);
  }, [companionId, destination, router, setActiveCompanionId]);

  if (roster.isLoading || requestedConversation.isLoading || recentConversations.isLoading || destination) {
    return <DataState kind="loading" title="正在进入对话" description="正在确认伙伴作用域与最近的真实会话。" />;
  }
  if (roster.isError || recentConversations.isError) {
    return <DataState kind="error" title="暂时无法进入对话" description="伙伴或会话列表读取失败；没有创建替代会话。" action={<Link className="echora-state-action" href="/">返回伙伴首页</Link>} />;
  }
  if (scopeMismatch || requestedConversation.isError) {
    return <DataState kind="error" title="无法确认这个对话入口" description="请求的伙伴或会话不属于当前可用的 Companion scope；Echora 不会跨伙伴猜测或回退。" action={<Link className="echora-state-action" href="/">重新选择伙伴</Link>} />;
  }
  return <DataState kind="empty" title="还没有可进入的伙伴" description="先在 Single Companion 首页认识或恢复一位伙伴，再开始对话。" action={<Link className="echora-state-action" href="/">前往伙伴首页</Link>} />;
}
