"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Check, Clock3, HeartHandshake, ShieldCheck, Users, X } from "lucide-react";
import { DataState } from "@/components/patterns/DataState";
import { ConfirmActionDialog } from "@/components/patterns/ConfirmActionDialog";
import { Pagination, usePageParam } from "@/components/patterns/Pagination";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";
import { companionWorkspaceApi, type ReviewInboxReadModel } from "@/lib/api/companionWorkspace";
import { decideReviewItem, type ReviewDecision } from "@/lib/review/reviewDecision";

type InboxItem = ReviewInboxReadModel["items"][number];
type Decision = ReviewDecision;
const REVIEW_PAGE_SIZE = 8;

const kindCopy: Record<InboxItem["kind"], string> = {
  memory: "私有记忆",
  growth: "成长建议",
  persona_growth: "人格成长",
  private_to_shared: "私有转共享",
  shared_to_private: "共享收录",
  cross_companion: "跨伙伴边界",
  channel: "频道记忆",
  realtime_shared: "实时共享记忆",
  relationship: "关系理解",
};

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "时间待确认" : date.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
}

function decisionCopy(item: InboxItem, decision: Decision) {
  if (decision === "reject") return { title: "拒绝此项审核", confirmLabel: "确认拒绝", description: "这项候选不会跨过当前伙伴的审核边界；处理结果会保留在领域审计中。" };
  if (item.kind === "memory") return { title: "确认并写入私有记忆", confirmLabel: "确认写入", description: "这会先接受候选，再写入当前伙伴的长期私有记忆。不会共享给其他伙伴。" };
  if (item.kind === "growth") return { title: "确认这项成长", confirmLabel: "确认成长", description: "这会将成长候选提交到当前伙伴范围，并保留可追溯记录。" };
  if (item.kind === "relationship") return { title: "确认这项关系理解", confirmLabel: "确认理解", description: "确认后才会以有界证据更新当前伙伴的关系状态，并保留可撤回 revision。" };
  if (item.kind === "channel") return { title: "确认频道记忆候选", confirmLabel: "确认审核", description: "这会通过既有频道边界流程处理候选；原始频道载荷不会显示在收件箱中。" };
  if (item.kind === "realtime_shared") return { title: "确认实时共享记忆候选", confirmLabel: "确认候选", description: "这只记录当前审核决定，不会自动写入共享记忆；后续共享仍需经过独立审核。" };
  return { title: "确认审核决定", confirmLabel: "确认决定", description: "这会通过既有共享与跨伙伴审核流程写入决定，并保留审计证据。" };
}

export function ReviewInbox() {
  const companion = useActiveCompanionContext();
  const [page, setPage] = usePageParam();
  const [scopePage, setScopePage] = usePageParam("scope_page");
  const [kind, setKind] = useState<InboxItem["kind"] | "all">("all");
  const [selected, setSelected] = useState<InboxItem | null>(null);
  const [pending, setPending] = useState<{ item: InboxItem; decision: Decision } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const inbox = useQuery({
    queryKey: ["review-inbox", companion.activeCompanionId, kind, page],
    queryFn: () => companionWorkspaceApi.reviewInboxPage(companion.activeCompanionId, REVIEW_PAGE_SIZE, (page - 1) * REVIEW_PAGE_SIZE, kind === "all" ? undefined : kind),
    enabled: !companion.allCompanions && Boolean(companion.activeCompanionId),
  });
  const items = inbox.data?.items ?? [];
  const selectedOnPage = selected ? items.find((item) => item.id === selected.id && item.kind === selected.kind) ?? null : null;
  const canDecide = Boolean(selectedOnPage);
  const totalReviews = useMemo(() => {
    const counts = inbox.data?.counts ?? {};
    const countedTotal = Object.keys(kindCopy).reduce((sum, entryKind) => sum + (counts[entryKind] ?? 0), 0);
    return counts.total ?? (countedTotal || inbox.data?.total || 0);
  }, [inbox.data?.counts, inbox.data?.total]);
  const inboxPagination = inbox.data ? {
    page,
    page_size: inbox.data.limit,
    total: inbox.data.total,
    total_pages: Math.max(1, Math.ceil(inbox.data.total / Math.max(1, inbox.data.limit))),
  } : undefined;
  const scopeItems = useMemo(() => companion.companions.slice((scopePage - 1) * REVIEW_PAGE_SIZE, scopePage * REVIEW_PAGE_SIZE), [companion.companions, scopePage]);
  const scopePagination = {
    page: scopePage,
    page_size: REVIEW_PAGE_SIZE,
    total: companion.companions.length,
    total_pages: Math.max(1, Math.ceil(companion.companions.length / REVIEW_PAGE_SIZE)),
  };

  function selectKind(nextKind: InboxItem["kind"] | "all") {
    setKind(nextKind);
    setSelected(null);
    setPage(1);
  }

  async function confirm() {
    if (!pending) return;
    setSaving(true);
    setActionError(null);
    try {
      await decideReviewItem(pending.item, pending.decision);
      setPending(null);
      setSelected(null);
      if (page > 1 && items.length === 1) setPage(page - 1);
      else await inbox.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "审核决定未能保存，请检查连接后重试。");
    } finally {
      setSaving(false);
    }
  }

  if (companion.allCompanions) return <main className="review-inbox review-inbox-overview">
    <header className="review-inbox-hero">
      <div><p>伙伴空间 / 审核收件箱</p><h1>每位伙伴都有<br />自己的待确认事项。</h1></div>
      <aside><Users size={18} aria-hidden="true" /><span>全部伙伴</span><strong>先选择范围，再作决定</strong><p>这里不会合并或执行跨伙伴审核；请使用设置左栏的伙伴选择器，或从下方选择一位伙伴。</p></aside>
    </header>
    <section className="review-inbox-overview-list" aria-label="伙伴审核范围">
      {companion.loading ? <DataState kind="loading" title="正在读取伙伴范围" /> : companion.companions.length ? <><div className="review-scope-page">{scopeItems.map((item) => <button type="button" key={item.id} onClick={() => companion.setActiveCompanionId(item.id)}><HeartHandshake size={17} /><span><strong>{item.name}</strong><small>{item.relationship_role || item.current_mode || "独立伙伴范围"}</small></span><ArrowRight size={16} aria-hidden="true" /></button>)}</div><Pagination pagination={scopePagination} page={scopePage} onPageChange={setScopePage} /></> : <DataState kind="empty" title="暂时没有可选择的伙伴" description="创建或恢复伙伴后，它会在这里显示独立审核范围。" />}
    </section>
  </main>;
  if (inbox.isError) return <DataState kind="error" title="审核收件箱暂不可用" description="请确认 Agent API 基线和当前连接后重试。" action={<button type="button" onClick={() => void inbox.refetch()}>重新读取</button>} />;

  return <main className="review-inbox">
    <header className="review-inbox-hero">
      <div>
        <p>伙伴空间 / 审核收件箱</p>
        <h1>把重要的决定，<br />留给你和 {companion.activeCompanion?.name ?? "这位伙伴"}。</h1>
      </div>
      <aside><HeartHandshake size={18} aria-hidden="true" /><span>当前伙伴范围</span><strong>{companion.activeCompanion?.name ?? "伙伴"}</strong><p>共享、频道与实时内容都需要明确审核，不能自动跨过边界。</p></aside>
    </header>

    <section className="review-inbox-summary" aria-label="审核收件箱摘要">
      <ShieldCheck size={18} aria-hidden="true" />
      <div><strong>{totalReviews} 项等待你的决定</strong><p>每一项都保留来源、范围和处理证据；不会把原始跨边界内容混入这里。</p></div>
    </section>

    <div className="review-inbox-layout">
      <section className="review-inbox-list" aria-label="审核队列">
        <div className="review-filter" role="group" aria-label="按审核类型筛选">
          <button type="button" className={kind === "all" ? "is-selected" : ""} aria-pressed={kind === "all"} onClick={() => selectKind("all")}>全部 <span>{totalReviews}</span></button>
          {Object.entries(inbox.data?.counts ?? {}).filter(([entryKind, count]) => entryKind in kindCopy && count > 0).map(([entryKind, count]) => <button type="button" key={entryKind} className={kind === entryKind ? "is-selected" : ""} aria-pressed={kind === entryKind} onClick={() => selectKind(entryKind as InboxItem["kind"])}>{kindCopy[entryKind as InboxItem["kind"]]} <span>{count}</span></button>)}
        </div>
        {inbox.isLoading ? <DataState kind="loading" title="正在读取审核事项" description="已确认伙伴范围，正在读取安全摘要。" /> : items.length ? <><div className="review-list">{items.map((item) => <button type="button" key={`${item.kind}-${item.id}`} className={`review-row ${selectedOnPage?.id === item.id ? "is-selected" : ""}`} onClick={() => setSelected(item)}><span className="review-row-icon"><ArrowRight size={15} /></span><span className="review-row-copy"><small>{kindCopy[item.kind]}{item.risk_level ? ` · ${item.risk_level} 风险` : ""}</small><strong>{item.title}</strong><em>{item.summary}</em><time><Clock3 size={12} />{formatTime(item.created_at)}</time></span></button>)}</div><Pagination pagination={inboxPagination} page={page} onPageChange={(nextPage) => { setSelected(null); setPage(nextPage); }} disabled={inbox.isFetching} /></> : <DataState kind="empty" title={kind === "all" ? "此刻没有等待决定的事项" : "这个类型暂时没有待审核事项"} description="当伙伴需要你确认记忆、成长、共享或频道边界时，它会在这里出现。" />}
      </section>

      <aside className="review-inspector" aria-live="polite">
        {selectedOnPage ? <><small>审核详情</small><h2>{selectedOnPage.title}</h2><p>{selectedOnPage.summary}</p><dl><div><dt>类型</dt><dd>{kindCopy[selectedOnPage.kind]}</dd></div><div><dt>当前状态</dt><dd>{selectedOnPage.status}</dd></div><div><dt>风险</dt><dd>{selectedOnPage.risk_level ?? "已按默认安全边界处理"}</dd></div><div><dt>来源</dt><dd>{selectedOnPage.source_id ? "已关联领域证据" : "由当前伙伴范围生成"}</dd></div></dl>{actionError ? <p className="review-action-error" role="alert">{actionError}</p> : null}{canDecide ? <div className="review-inspector-actions"><button type="button" onClick={() => setPending({ item: selectedOnPage, decision: "approve" })}><Check size={15} />确认</button><button type="button" onClick={() => setPending({ item: selectedOnPage, decision: "reject" })}><X size={15} />拒绝</button></div> : <div className="review-unavailable"><AlertTriangle size={16} /><p>此类候选已被安全收集，但当前运行基线尚未提供可执行的领域决策接口，因此不会在此伪造操作。</p></div>}</> : <div className="review-inspector-empty"><ShieldCheck size={20} /><h2>先选择一项审核</h2><p>你会看到它属于哪位伙伴、会影响什么，以及确认后会发生什么。</p></div>}
      </aside>
    </div>
    {pending ? <ConfirmActionDialog {...decisionCopy(pending.item, pending.decision)} cancelLabel="暂不处理" busy={saving} onConfirm={() => void confirm()} onCancel={() => setPending(null)} /> : null}
  </main>;
}
