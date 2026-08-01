"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HeartHandshake, RotateCcw, ShieldCheck } from "lucide-react";
import {
  SettingsAction,
  SettingsInlineNotice,
  SettingsSectionHeading,
  SettingsStatusPill,
} from "@/components/settings/SettingsControls";
import { relationshipApi, type RelationshipCandidate } from "@/lib/api/relationships";

const labels: Record<string, string> = { familiarity: "熟悉程度", understanding: "相互理解", collaboration: "协作默契", trust: "信任", emotional_closeness: "情感亲近", boundary_awareness: "边界理解", continuity: "相处延续" };

export function RelationshipEvolutionPanel({ companionId }: { companionId: string }) {
  const client = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const stateQuery = useQuery({ queryKey: ["relationship", companionId, "state"], queryFn: () => relationshipApi.state(companionId) });
  const candidateQuery = useQuery({ queryKey: ["relationship", companionId, "candidates"], queryFn: () => relationshipApi.candidates(companionId, "pending") });
  const revisionQuery = useQuery({ queryKey: ["relationship", companionId, "revisions"], queryFn: () => relationshipApi.revisions(companionId) });
  const refresh = async () => { await Promise.all([client.invalidateQueries({ queryKey: ["relationship", companionId] }), client.invalidateQueries({ queryKey: ["companions", companionId, "chronicle"] })]); };
  const commit = useMutation({ mutationFn: (candidate: RelationshipCandidate) => relationshipApi.commit(companionId, candidate), onMutate: () => setActionError(null), onSuccess: refresh, onError: (error) => setActionError(error instanceof Error ? error.message : "暂时无法确认关系理解") });
  const reject = useMutation({ mutationFn: (id: string) => relationshipApi.reject(companionId, id), onMutate: () => setActionError(null), onSuccess: refresh, onError: (error) => setActionError(error instanceof Error ? error.message : "暂时无法拒绝候选") });
  const correct = useMutation({ mutationFn: ({ id, revision }: { id: string; revision: number }) => relationshipApi.correct(companionId, id, revision), onMutate: () => setActionError(null), onSuccess: refresh, onError: (error) => setActionError(error instanceof Error ? error.message : "暂时无法撤回当前理解") });
  if (stateQuery.isLoading || candidateQuery.isLoading || revisionQuery.isLoading) return <section className="settings-domain-section"><SettingsInlineNotice>正在读取关系演化…</SettingsInlineNotice></section>;
  if (stateQuery.isError || candidateQuery.isError || revisionQuery.isError) return <section className="settings-domain-section"><SettingsInlineNotice tone="danger">暂时无法读取关系演化。</SettingsInlineNotice></section>;
  const state = stateQuery.data;
  const candidates = candidateQuery.data?.items ?? [];
  const currentRevision = revisionQuery.data?.items.find((item) => item.id === state?.current_revision_id);
  return <section className="settings-domain-section settings-relationship-section" aria-labelledby="relationship-evolution-title">
    <SettingsSectionHeading
      id="relationship-evolution-title"
      icon={HeartHandshake}
      title="我们正在怎样理解彼此"
      description="关系理解只来自已确认的相处证据；候选在你确认前不会改变当前状态。"
      action={<SettingsStatusPill>版本 {state?.revision ?? 0}</SettingsStatusPill>}
    />
    <div className="settings-relationship-grid"><div><h3>当前理解</h3>
      {!state ? <p className="settings-muted-copy">尚无已确认的关系变化。第一次确认后才会建立状态。</p> : <div className="settings-dimension-grid">{Object.entries(state.uncertainty ?? {}).map(([dimension, stats]) => <div key={dimension} className="settings-dimension-row"><div><span>{labels[dimension] ?? dimension}</span><strong>{confidenceLabel(stats.interval_high - stats.interval_low)}</strong></div><p>{positionLabel(stats.mean)} · 证据强度 {evidenceLabel(stats.effective_evidence)}</p></div>)}</div>}
      {currentRevision ? <SettingsAction disabled={correct.isPending} onClick={() => correct.mutate({ id: currentRevision.id, revision: state?.revision ?? 0 })}><RotateCcw size={14} aria-hidden="true" />撤回当前一次理解</SettingsAction> : null}
    </div><div><div className="settings-subsection-title"><h3>待你确认</h3><SettingsStatusPill tone="warning">{candidates.length} 条</SettingsStatusPill></div>
      {candidates.length === 0 ? <p className="settings-muted-copy">当前没有待确认的关系理解。</p> : <div className="settings-record-list">{candidates.map((candidate) => <article key={candidate.id}><div className="settings-record-heading"><h3>{candidate.summary}</h3><SettingsStatusPill tone="warning">{riskLabel(candidate.risk_level)}</SettingsStatusPill></div><div className="settings-record-meta">{candidate.dimension_signals.map((signal) => <span key={signal.dimension}>{labels[signal.dimension] ?? signal.dimension} · {signal.direction === "increase" ? "增强" : "减弱"}</span>)}</div>{candidate.evidence_quotes.map((quote, index) => quote.user ? <blockquote key={`${candidate.id}-${index}`}>“{quote.user}”</blockquote> : null)}<p className="settings-record-note"><ShieldCheck size={13} aria-hidden="true" />人工确认前不会改变关系状态</p><div className="settings-record-actions"><SettingsAction variant="primary" disabled={commit.isPending || reject.isPending} onClick={() => commit.mutate(candidate)}>确认理解</SettingsAction><SettingsAction disabled={commit.isPending || reject.isPending} onClick={() => reject.mutate(candidate.id)}>不采用</SettingsAction></div></article>)}</div>}
    </div></div>{actionError ? <SettingsInlineNotice tone="danger">{actionError}。若页面已打开较久，请刷新后重试。</SettingsInlineNotice> : null}
  </section>;
}

function confidenceLabel(width: number) { return width >= 0.55 ? "证据仍少" : width >= 0.3 ? "逐步稳定" : "较稳定"; }
function positionLabel(mean: number) { return mean >= 0.72 ? "较高" : mean >= 0.48 ? "中等" : mean >= 0.28 ? "正在形成" : "尚浅"; }
function evidenceLabel(value: number) { return value >= 10 ? "充分" : value >= 5 ? "中等" : "有限"; }
function riskLabel(value: string) { return ({ low: "低风险", medium: "需留意", high: "高风险" } as Record<string, string>)[value] ?? "待确认"; }
