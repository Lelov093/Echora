"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenText, HeartHandshake, Lightbulb, LockKeyhole, MessageCircle, RotateCcw, Sparkles } from "lucide-react";
import { SettingsAction, SettingsInlineNotice, SettingsSectionHeading, SettingsStatusPill } from "@/components/settings/SettingsControls";
import { SettingsViewHeader } from "@/components/settings/SettingsView";
import { Pagination, usePageParam } from "@/components/patterns/Pagination";
import { companionWorkspaceApi, type ChronicleReadModel } from "@/lib/api/companionWorkspace";
import { useCompanionWorkspaceQuery } from "@/lib/queries/companions";
import { DataState } from "@/components/patterns/DataState";

const icons = { continuity: MessageCircle, growth: Sparkles, relationship: HeartHandshake, relationship_pending: HeartHandshake, memory: BookOpenText, presence: Lightbulb, companion: LockKeyhole } as const;
const labels: Record<string, string> = { continuity: "对话延续", growth: "共同成长", relationship: "关系演化", relationship_pending: "待确认理解", memory: "共同记忆", presence: "在场感", companion: "伙伴档案" };
type Item = ChronicleReadModel["items"][number];
const CHRONICLE_PAGE_SIZE = 6;

export function LivingChronicle({ companionId }: { companionId: string }) {
  const client = useQueryClient();
  const workspace = useCompanionWorkspaceQuery(companionId);
  const chronicle = useQuery({ queryKey: ["companions", companionId, "chronicle"], queryFn: () => companionWorkspaceApi.chronicle(companionId, 100) });
  const [page, setPage] = usePageParam("chronicle_page");
  const [selected, setSelected] = useState<Item | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const refresh = useMutation({ mutationFn: () => companionWorkspaceApi.refreshChronicleSummary(companionId), onMutate: () => setSummaryError(null), onSuccess: () => client.invalidateQueries({ queryKey: ["companions", companionId, "chronicle"] }), onError: (error) => setSummaryError(error instanceof Error ? error.message : "暂时无法生成阶段摘要") });
  const invalidate = useMutation({ mutationFn: (id: string) => companionWorkspaceApi.invalidateChronicleSummary(companionId, id, "用户指出该阶段摘要不准确"), onMutate: () => setSummaryError(null), onSuccess: () => client.invalidateQueries({ queryKey: ["companions", companionId, "chronicle"] }), onError: (error) => setSummaryError(error instanceof Error ? error.message : "暂时无法使摘要失效") });
  if (workspace.isLoading || chronicle.isLoading) return <DataState kind="loading" title="正在翻开共同历程" />;
  if (workspace.isError || chronicle.isError || !workspace.data || !chronicle.data) return <DataState kind="error" title="暂时无法读取共同历程" />;
  const activeSummary = chronicle.data.summaries?.find((summary) => summary.status === "active");
  const totalItems = chronicle.data.items.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / CHRONICLE_PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = chronicle.data.items.slice((currentPage - 1) * CHRONICLE_PAGE_SIZE, currentPage * CHRONICLE_PAGE_SIZE);
  const changePage = (nextPage: number) => {
    setSelected(null);
    setPage(nextPage);
  };
  return <section className="settings-native-view living-chronicle settings-chronicle-workspace">
    <SettingsViewHeader
      eyebrow="设置 / 共同历程"
      title="不是一段记录，而是持续发生的我们"
      description={`与 ${workspace.data.companion.name} 一起走过的时间。${workspace.data.identity.relationship_summary}`}
      icon={BookOpenText}
      aside={<><strong>独立而可追溯</strong><p>只汇集当前伙伴范围内已确认的事件，不把待确认内容写成共同事实。</p></>}
    />
    <section className="settings-domain-section chronicle-summary-section" aria-label="阶段性共同历程摘要">
      <SettingsSectionHeading
        icon={Sparkles}
        eyebrow="只来自已确认事件"
        title={activeSummary?.title ?? "还没有形成阶段摘要"}
        description="阶段摘要帮助回望共同历程，但不会反向改写关系、成长或记忆。"
        action={<SettingsAction variant="primary" busy={refresh.isPending} onClick={() => refresh.mutate()}>{activeSummary ? "重新生成" : "生成阶段摘要"}</SettingsAction>}
      />
      {activeSummary ? <div className="chronicle-summary-content"><p>{activeSummary.summary}</p><ul>{activeSummary.highlights.map((item) => <li key={item}>{item}</li>)}</ul><div className="settings-record-actions"><SettingsStatusPill>版本 {activeSummary.version}</SettingsStatusPill><SettingsStatusPill tone="success">{activeSummary.source_event_refs.length} 条确认依据</SettingsStatusPill><SettingsAction disabled={invalidate.isPending} onClick={() => invalidate.mutate(activeSummary.id)}><RotateCcw size={14} aria-hidden="true" />标记摘要不准确</SettingsAction></div></div> : <SettingsInlineNotice>至少三条已确认历程事件后，可由真实 Provider 生成可追溯摘要。</SettingsInlineNotice>}
      {summaryError ? <SettingsInlineNotice tone="danger">{summaryError}</SettingsInlineNotice> : null}
    </section>
    <div className="chronicle-layout"><main className="chronicle-timeline">{totalItems ? <><ol className="chronicle-list">{pageItems.map((item) => { const Icon = icons[item.kind as keyof typeof icons] ?? BookOpenText; return <li key={item.id}><span className={`chronicle-icon is-${item.kind}`}><Icon size={18} /></span><button type="button" onClick={() => setSelected(item)}><small>{labels[item.kind] || "共同历程"} · {new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium" }).format(new Date(item.occurred_at))}</small><h2>{item.title}</h2><p>{item.summary}</p>{item.trace_id ? <span className="chronicle-trace">有回应依据</span> : null}{item.review_status ? <span className="chronicle-status">{statusLabel(item.review_status)}</span> : null}</button></li>; })}</ol><Pagination pagination={{ page: currentPage, page_size: CHRONICLE_PAGE_SIZE, total: totalItems, total_pages: totalPages }} page={currentPage} onPageChange={changePage} /></> : <DataState kind="empty" title="共同历程刚刚开始" description="对话、确认的记忆、成长与关系变化会在这里留下可追溯的痕迹。" />}</main>
      <aside>{selected ? <section className="chronicle-inspector"><small>这次变化</small><h2>{selected.title}</h2><p><strong>来自</strong>{labels[selected.kind] || "共同历程"} · 仅限当前伙伴</p><p><strong>现在</strong>{statusLabel(selected.review_status)}</p><p><strong>会怎样影响相处</strong>{selected.kind === "relationship_pending" ? "仍待你的确认，不会改变当前关系。" : "保留为你们的共同历程，不会进入其他伙伴的私有内容。"}</p>{selected.trace_id ? <p><strong>回复依据</strong>需要排查时可在高级证据中定位；普通历程不展示内部编号。</p> : null}<Link className="chronicle-context-action" href={contextHref(companionId, selected.kind)}>{contextLabel(selected.kind)}</Link></section> : <section><LockKeyhole size={18} /><div><small>独立保存</small><h2>只属于你和 {workspace.data.companion.name}</h2><p>选择一条变化，了解它现在意味着什么，以及你可以去哪里调整。</p></div></section>}</aside>
    </div>
  </section>;
}

function statusLabel(status: string | null) {
  const labelsByStatus: Record<string, string> = { active: "已确认", committed: "已确认", corrected: "已纠正", reverted: "已撤回", pending_review: "待确认", candidate: "待确认", rejected: "已拒绝", invalidated: "已失效" };
  return status ? labelsByStatus[status] ?? status : "已记录";
}

function contextHref(companionId: string, kind: string) {
  if (kind === "memory") return `/settings/companions/${companionId}/memory`;
  if (kind === "growth" || kind.startsWith("relationship")) return `/settings/companions/${companionId}/growth`;
  if (kind === "presence") return `/settings/companions/${companionId}/presence`;
  return `/companions/${companionId}/profile`;
}
function contextLabel(kind: string) {
  if (kind === "memory") return "调整这位伙伴的记忆";
  if (kind === "growth" || kind.startsWith("relationship")) return "查看成长与关系理解";
  if (kind === "presence") return "调整陪伴方式";
  return "打开伙伴档案";
}
