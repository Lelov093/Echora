"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Activity, Bot, Check, CircleAlert, ShieldCheck } from "lucide-react";
import {
  getGovernancePolicy,
  getQualityFeedbackOverview,
  rollbackGovernancePolicy,
  updateGovernancePolicy,
  type GovernanceDomainOverride,
  type GovernanceMode,
  type GovernancePolicy,
} from "@/lib/api/settings";

const MODES: Array<{ key: GovernanceMode; label: string; description: string }> = [
  { key: "partial_auto", label: "部分自动", description: "推荐。低风险私有记忆可自动，其余持久变化仍由你确认。" },
  { key: "full_auto", label: "全自动", description: "启用当前所有受支持自动化；未支持领域仍保持人工与安全门槛。" },
  { key: "manual", label: "手动治理", description: "所有领域变更由你确认；后台检测与质量建议仍持续记录。" },
];

const EFFECTIVE_LABELS = {
  automatic: "自动执行",
  automatic_feedback: "自动检测与建议",
  manual: "人工确认",
} as const;

export function GovernanceAutomationPanel({ companionId }: { companionId?: string | null }) {
  const queryClient = useQueryClient();
  const queryKey = ["governance-policy", companionId];
  const policy = useQuery({
    queryKey,
    queryFn: () => getGovernancePolicy(companionId!),
    enabled: Boolean(companionId),
  });
  const quality = useQuery({
    queryKey: ["quality-feedback", companionId],
    queryFn: () => getQualityFeedbackOverview(companionId!),
    enabled: Boolean(companionId),
    refetchInterval: 10_000,
  });
  const save = useMutation({
    mutationFn: (next: { mode: GovernanceMode; domain_overrides: GovernancePolicy["domain_overrides"]; expected_revision: number }) =>
      updateGovernancePolicy(companionId!, next),
    onSuccess: (next) => queryClient.setQueryData(queryKey, next),
    onError: () => void policy.refetch(),
  });
  const rollback = useMutation({
    mutationFn: (revision: number) => rollbackGovernancePolicy(companionId!, revision),
    onSuccess: (next) => queryClient.setQueryData(queryKey, next),
    onError: () => void policy.refetch(),
  });
  if (!companionId) {
    return <section className="governance-panel governance-panel-state"><CircleAlert size={18} /><p>请先选择一位伙伴，再配置治理方式。</p></section>;
  }
  if (policy.isLoading) {
    return <section className="governance-panel governance-panel-state"><Bot size={18} /><p>正在读取这位伙伴的治理策略…</p></section>;
  }
  if (!policy.data || policy.isError) {
    return <section className="governance-panel governance-panel-state"><CircleAlert size={18} /><div><p>治理策略暂时不可用。</p><button type="button" onClick={() => void policy.refetch()}>重试</button></div></section>;
  }

  const current = policy.data;
  const qualityDomain = current.domains.find((domain) => domain.key === "quality");
  const qualityEnabled = qualityDomain?.effective_mode === "automatic_feedback";
  const persist = (mode: GovernanceMode, domainOverrides = current.domain_overrides) => {
    save.mutate({ mode, domain_overrides: domainOverrides, expected_revision: current.revision });
  };

  return (
    <section className="governance-panel" aria-labelledby="governance-title">
      <header>
        <div><small>GOVERNANCE AUTOMATION</small><h2 id="governance-title">让治理留在后台</h2><p>你选择参与程度，Echora 负责执行可验证的流程。安全边界不会随模式降低。</p></div>
        <span><ShieldCheck size={15} />策略版本 {current.revision}</span>
      </header>

      <div className="governance-mode-list" role="radiogroup" aria-label="治理模式">
        {MODES.map((mode) => <button
          type="button"
          role="radio"
          aria-checked={current.mode === mode.key}
          className={current.mode === mode.key ? "is-selected" : ""}
          disabled={save.isPending || rollback.isPending}
          key={mode.key}
          onClick={() => persist(mode.key)}
        ><span>{current.mode === mode.key ? <Check size={16} /> : null}<strong>{mode.label}</strong></span><small>{mode.description}</small></button>)}
      </div>

      <section className="governance-quality" aria-labelledby="governance-quality-title">
        <div className="governance-domain-heading">
          <div><h3 id="governance-quality-title">后台质量反馈</h3><p>Trace 完成后，以持久任务形成 Evaluation、Bad Case 与 Regression 建议；不会自动改写伙伴状态。</p></div>
          <span className={quality.data?.scheduler.enabled && qualityEnabled ? "is-running" : ""}><Activity size={14} />{quality.data?.scheduler.enabled && qualityEnabled ? "分析建议已开启" : "自动分析已关闭"}</span>
        </div>
        {quality.isLoading ? <p className="governance-quality-state">正在读取质量闭环…</p> : null}
        {quality.isError ? <p className="governance-quality-state is-error">质量反馈暂时不可用，不影响伙伴对话与现有 Trace。</p> : null}
        {quality.data ? <>
          <div className="governance-quality-metrics">
            <article><strong>{quality.data.run_counts.completed}</strong><span>已完成检查</span></article>
            <article><strong>{quality.data.run_counts.pending + quality.data.run_counts.running}</strong><span>等待 / 运行中</span></article>
            <article><strong>{quality.data.run_counts.failed}</strong><span>Worker 失败</span></article>
            <article><strong>{Object.entries(quality.data.bad_case_counts).filter(([key]) => !["resolved", "dismissed"].includes(key)).reduce((sum, [, value]) => sum + value, 0)}</strong><span>待处理 Bad Case</span></article>
          </div>
          <p className="governance-quality-boundary">自动分析建议：{qualityEnabled ? "开启" : "关闭"} · 自动应用伙伴变化：始终关闭 · 原始消息复制：始终关闭</p>
          <div className="governance-quality-domains" aria-label="质量反馈来源领域">
            {Object.entries(quality.data.domain_counts).map(([domain, count]) => (
              <span key={domain}>{qualityDomainLabel(domain)} {count}</span>
            ))}
          </div>
          {quality.data.latest_runs.length ? <ol className="governance-quality-runs">
            {quality.data.latest_runs.slice(0, 6).map((run) => <li key={run.id}>
              <span className={`is-${run.status}`}>{run.status === "completed" ? "已检查" : run.status === "running" ? "检查中" : run.status === "pending" ? "等待" : "失败"}</span>
              <code>{qualityDomainLabel(run.source_domain)} · {run.source_entity_type} · {run.source_entity_id?.slice(0, 8) || "无标识"} · r{run.feedback_revision}</code>
              <small>{run.aggregate_score === null ? "尚无评分" : `确定性得分 ${Math.round(run.aggregate_score * 100)}%`}</small>
            </li>)}
          </ol> : <p className="governance-quality-state">还没有质量反馈记录；下一条完成的 Trace 会自动进入。</p>}
          <Link className="governance-quality-link" href="/settings/quality">查看质量证据与处理操作</Link>
        </> : null}
      </section>

      <div className="governance-domain-list">
        <div className="governance-domain-heading"><h3>按领域调整</h3><p>“自动”不可用时会明确降为人工确认，不会伪造能力。</p></div>
        {current.domains.map((domain) => <article key={domain.key}>
          <div><strong>{domain.label}</strong><span className={`governance-effective is-${domain.effective_mode}`}>{EFFECTIVE_LABELS[domain.effective_mode]}</span></div>
          <p>{domainDescription(domain.automation_support, domain.support_status)}</p>
          <label><span>覆盖</span><select
            aria-label={`${domain.label}治理覆盖`}
            value={domain.override}
            disabled={save.isPending || rollback.isPending}
            onChange={(event) => persist(current.mode, {
              ...current.domain_overrides,
              [domain.key]: event.target.value as GovernanceDomainOverride,
            })}
          ><option value="inherit">跟随整体设置</option><option value="automatic" disabled={!domain.automatic_available}>{domain.key === "quality" ? "开启分析建议" : "自动"}</option><option value="manual">{domain.key === "quality" ? "关闭自动分析" : "人工确认"}</option></select></label>
        </article>)}
      </div>

      <footer>
        <span>Memory reranker：{current.learned_policy_status.memory_reranker}</span>
        <span>Presence bandit：{current.learned_policy_status.contextual_presence_bandit}</span>
        <span>可回滚版本：{current.history_count}</span>
        <button type="button" disabled={!current.can_rollback || save.isPending || rollback.isPending} onClick={() => rollback.mutate(current.revision)}>撤回上一次策略修改</button>
        {save.isError ? <strong>保存冲突或失败，已重新读取最新策略。</strong> : null}
        {rollback.isError ? <strong>撤回失败，已重新读取最新策略。</strong> : null}
      </footer>
    </section>
  );
}

function domainDescription(support: string, status: string) {
  if (support === "low_risk_private_commit") return "仅严格低风险的伙伴私有记忆可自动保存；敏感、更正、共享与跨伙伴内容始终确认。";
  if (support === "trace_evaluation_bad_case_regression") return "开启后会在对话完成时生成分析与改进建议；关闭后仍可由你手动发起检查，建议永远不会自动改写伙伴。";
  if (support === "automatic_detection_manual_apply") return "系统可自动识别候选和证据，持久成长或关系变化仍需独立确认。";
  if (support === "bounded_runtime_separate_correction_gate") return "仅使用既有有界情绪运行机制；更正、表达关闭和边界变化仍走独立入口。";
  if (support === "schedule_policy_separate") return "主动联系由独立日程、静默和边界策略控制，治理预设不能绕过它们。";
  if (support === "risk_gated_runtime") return "低风险工具可执行；外发、写入、不可逆和高风险操作继续显式确认。";
  if (support === "binding_and_outbox_gated") return "渠道行为受绑定、权限、mention、outbox 与 revoke 控制，治理预设不能自动改绑。";
  if (support === "review_gated_only") return "共享、跨伙伴与渠道记忆始终 review-gated，不提供自动应用。";
  if (status === "not_yet_supported") return "当前只提供分析或规划，持久写入尚未接入安全自动化，因此继续人工确认。";
  return "当前领域保持人工确认。";
}

function qualityDomainLabel(domain: string) {
  return ({
    quality: "对话运行",
    presence: "主动联系",
    tools: "工具",
    channels: "渠道",
    shared: "共享审查",
  } as Record<string, string>)[domain] || domain;
}
