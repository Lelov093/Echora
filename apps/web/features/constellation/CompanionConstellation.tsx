"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, LockKeyhole, Plus, ShieldCheck, Sparkles } from "lucide-react";
import { CompanionOrb } from "@/components/companion/CompanionOrb";
import { CompanionCreatePanel } from "@/components/companions/CompanionCreatePanel";
import { DataState } from "@/components/patterns/DataState";
import { createCompanion } from "@/lib/api/companions";
import { companionHousehold, companionKeys, useCompanionReviewTotal, useCompanionRosterQuery } from "@/lib/queries/companions";

function statusLabel(status?: string | null) {
  return status === "active" || status === "online" ? "正在陪伴" : status === "busy" ? "专注中" : "安静在场";
}

export function CompanionConstellation() {
  const [creating, setCreating] = useState(false);
  const [archivedOpen, setArchivedOpen] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();
  const roster = useCompanionRosterQuery();
  const archivedRoster = useCompanionRosterQuery("archived");
  const household = companionHousehold(roster.data?.items ?? []);
  const companions = household.slice(0, 6);
  const reviewTotal = useCompanionReviewTotal();
  const create = useMutation({ mutationFn: createCompanion, onSuccess: async (companion) => {
    await queryClient.invalidateQueries({ queryKey: companionKeys.roster("product") });
    router.push(companion.first_meeting_conversation_id ? `/companions/${companion.id}/conversations/${companion.first_meeting_conversation_id}` : `/companions/${companion.id}`);
  } });

  if (roster.isLoading) return <DataState kind="loading" title="正在点亮伙伴星图" description="正在确认每位伙伴的独立空间。" />;
  if (roster.isError) return <DataState kind="error" title="暂时无法抵达伙伴星图" description="请确认 Agent API 正在运行后重试。" />;
  if (!companions.length && !creating) return <DataState kind="empty" title="从第一次相识开始" description="建立一段有边界、可延续的伙伴关系。" action={<><button type="button" onClick={() => setCreating(true)}>认识一位新伙伴</button>{archivedRoster.data?.items.length ? <button type="button" onClick={() => setArchivedOpen(true)}>查看已归档关系</button> : null}</>} />;

  const focused = companions.findIndex((companion) => Boolean(companion.current_focus));
  const recommendedIndex = focused >= 0 ? focused : 0;

  return (
    <section className="constellation-page">
      <div className="constellation-copy">
        <span className="constellation-eyebrow"><Sparkles size={15} /> 伙伴星图</span>
        <h1>你的伙伴们，<br />各自闪耀，也彼此和谐</h1>
        <p>{household.length > 6 ? `最近活跃的 ${companions.length} 位伙伴` : `${companions.length} 位伙伴`}，共同陪伴。每段关系、记忆与边界都独立保存。</p>
        <button type="button" className="constellation-create-link" onClick={() => setCreating(true)}><Plus size={17} /> 认识一位新伙伴</button>
        {reviewTotal > 0 ? <Link className="constellation-review-link" href="/review"><ShieldCheck size={17} /> {reviewTotal} 项决定等待确认 <ArrowRight size={16} /></Link> : null}
        {archivedRoster.data?.items.length ? <button type="button" className="constellation-archive-link" onClick={() => setArchivedOpen(true)}>查看 {archivedRoster.data.items.length} 段已归档关系</button> : null}
      </div>
      <div className={`constellation-field has-${Math.min(companions.length, 6)}`}>
        <span className="constellation-orbit orbit-one" aria-hidden="true" />
        <span className="constellation-orbit orbit-two" aria-hidden="true" />
        {companions.map((companion, index) => {
          return (
            <Link key={companion.id} href={`/companions/${companion.id}`} className={`constellation-companion companion-${(index % 6) + 1}`}>
              <CompanionOrb name={companion.name} index={index} size={companions.length >= 5 ? "medium" : index === recommendedIndex ? "large" : "medium"} />
              <span className="constellation-companion-copy">
                <strong>{companion.name}</strong>
                <small>{companion.relationship_role || "长期伙伴"}</small>
                <em><i />{statusLabel(companion.current_status)}</em>
                <span>{companion.current_focus || "在自己的节奏里陪着你"}</span>
                <b><LockKeyhole size={12} /> 私有空间</b>
              </span>
            </Link>
          );
        })}
      </div>
      <p className="constellation-boundary-note"><ShieldCheck size={16} /> 每位伙伴只在自己的私有边界内工作；共享连接必须经过你的确认。<Link href="/companions">高级伙伴注册表</Link></p>
      {creating ? <div className="companion-create-backdrop" role="presentation"><div className="companion-create-dialog" role="dialog" aria-modal="true" aria-label="认识一位新伙伴"><CompanionCreatePanel creating={create.isPending} message={create.error instanceof Error ? create.error.message : null} onCreate={async (payload) => { await create.mutateAsync(payload); }} onCancel={() => setCreating(false)} /></div></div> : null}
      {archivedOpen ? <div className="companion-create-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setArchivedOpen(false); }}><aside className="constellation-archive-dialog" role="dialog" aria-modal="true" aria-label="已归档关系"><header><div><small>关系生命周期</small><h2>已归档的关系</h2></div><button type="button" onClick={() => setArchivedOpen(false)}>关闭</button></header><p>归档不会删除共同历史。打开档案后，可重新确认边界与渠道状态并恢复。</p><nav>{archivedRoster.data?.items.map((companion) => <Link key={companion.id} href={`/companions/${companion.id}/profile`} onClick={() => setArchivedOpen(false)}><strong>{companion.name}</strong><span>{companion.relationship_role || "长期伙伴"}</span><ArrowRight size={16} /></Link>)}</nav></aside></div> : null}
    </section>
  );
}
