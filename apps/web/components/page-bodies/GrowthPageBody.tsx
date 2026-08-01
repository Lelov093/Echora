"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RotateCcw, Sparkles, Sprout, ThumbsDown, ThumbsUp } from "lucide-react";
import { ListControls } from "@/components/list/ListControls";
import {
  SettingsAction,
  SettingsInlineNotice,
  SettingsSectionHeading,
  SettingsStateSwitch,
  SettingsStatusPill,
} from "@/components/settings/SettingsControls";
import { RelationshipEvolutionPanel } from "@/features/growth/RelationshipEvolutionPanel";
import { createFeedbackEvent } from "@/lib/api/feedback";
import type { GrowthCandidate, GrowthRecord } from "@/lib/api/growth";
import { getGrowthSuggestionPolicy, saveGrowthSuggestionPolicy } from "@/lib/api/growth";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";
import { useClientListControls } from "@/lib/hooks/useClientListControls";
import { useGrowthJournal } from "@/lib/hooks/useGrowthJournal";

type FeedbackState = "sent" | "error" | "sending";
const GROWTH_DOMAINS = [
  { key: "understanding_update", label: "理解变化", description: "是否允许伙伴更新对你当前状态与处境的理解。" },
  { key: "preference", label: "偏好理解", description: "是否允许形成或修正对喜好、习惯与禁忌的理解。" },
  { key: "relationship", label: "关系理解", description: "是否允许提出双方关系定位与相处方式的变化。" },
  { key: "behavior", label: "互动方式", description: "是否允许调整帮助、协作、提醒与陪伴方式。" },
  { key: "communication_style", label: "沟通风格", description: "是否允许调整语气、表达详略与交流习惯。" },
] as const;

export default function GrowthPageBody() {
  const companionContext = useActiveCompanionContext();
  const growth = useGrowthJournal(companionContext.companionFilterId, companionContext.hydrated);
  const queryClient = useQueryClient();
  const [feedbackState, setFeedbackState] = useState<Record<string, FeedbackState>>({});
  const [policyFeedback, setPolicyFeedback] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [editingCandidate, setEditingCandidate] = useState<GrowthCandidate | null>(null);
  const [editedContent, setEditedContent] = useState("");
  const companionId = companionContext.activeCompanionId;
  const policyKey = ["growth-policy", companionId] as const;
  const policy = useQuery({
    queryKey: policyKey,
    queryFn: () => getGrowthSuggestionPolicy(companionId),
    enabled: Boolean(companionId),
  });
  const savePolicy = useMutation({
    mutationFn: (next: { suggestions_enabled: boolean; paused_types: string[] }) =>
      saveGrowthSuggestionPolicy(companionId, {
        ...next,
        expected_updated_at: policy.data?.updated_at ?? null,
      }),
    onMutate: async (next) => {
      setPolicyFeedback("saving");
      await queryClient.cancelQueries({ queryKey: policyKey });
      const previous = queryClient.getQueryData(policyKey);
      queryClient.setQueryData(policyKey, (current: typeof policy.data) => current ? { ...current, ...next } : current);
      return { previous };
    },
    onSuccess: (next) => {
      queryClient.setQueryData(policyKey, next);
      setPolicyFeedback("saved");
    },
    onError: (_error, _next, context) => {
      if (context?.previous) queryClient.setQueryData(policyKey, context.previous);
      setPolicyFeedback("error");
    },
  });
  const recordList = useClientListControls<GrowthRecord>({
    items: growth.records,
    searchText: (item) => `${item.type ?? ""} ${item.summary ?? ""} ${item.content ?? ""} ${item.reason ?? ""}`,
    status: (item) => item.status,
    initialPageSize: 10,
  });
  const candidateList = useClientListControls<GrowthCandidate>({
    items: growth.candidates,
    searchText: (item) => `${item.type ?? ""} ${item.content ?? ""} ${item.reason ?? ""}`,
    status: (item) => item.status,
    initialPageSize: 10,
  });

  const sendFeedback = async (targetId: string, action: "helpful" | "wrong") => {
    setFeedbackState((current) => ({ ...current, [targetId]: "sending" }));
    if (!companionContext.activeCompanion?.user_id) {
      setFeedbackState((current) => ({ ...current, [targetId]: "error" }));
      return;
    }
    try {
      await createFeedbackEvent({
        user_id: companionContext.activeCompanion.user_id,
        companion_id: companionContext.activeCompanionId,
        target_type: "growth_candidate",
        target_id: targetId,
        action,
        reason: action === "helpful" ? "Growth candidate was useful" : "Growth candidate was incorrect",
        context_json: { source: "GrowthPage" },
      });
      setFeedbackState((current) => ({ ...current, [targetId]: "sent" }));
    } catch {
      setFeedbackState((current) => ({ ...current, [targetId]: "error" }));
    }
  };

  if (growth.loading) {
    return <main className="settings-native-view"><SettingsInlineNotice>正在读取这位伙伴的成长记录…</SettingsInlineNotice></main>;
  }
  if (growth.error) {
    return <main className="settings-native-view"><SettingsInlineNotice tone="danger">暂时无法读取成长记录。<SettingsAction onClick={growth.reload}>重试</SettingsAction></SettingsInlineNotice></main>;
  }

  const committedCount = growth.records.filter((record) => record.status === "committed").length;
  const revertedCount = growth.records.filter((record) => record.status === "reverted").length;

  return (
    <main className="settings-growth-workspace">
      <section className="settings-summary-strip" aria-label="成长状态摘要">
        <p>所有变化均保留证据、状态与回滚入口。</p>
        <div>
          <SettingsStatusPill tone="warning">待确认 {growth.candidates.length}</SettingsStatusPill>
          <SettingsStatusPill tone="success">已确认 {committedCount}</SettingsStatusPill>
          <SettingsStatusPill>已撤回 {revertedCount}</SettingsStatusPill>
        </div>
      </section>

      <section className="settings-domain-section growth-control-section" aria-labelledby="growth-control-title">
        <SettingsSectionHeading
          id="growth-control-title"
          icon={Sparkles}
          title="成长建议由你决定"
          description="暂停后不再从新对话形成成长候选；已有记录、回滚证据和安全审计仍会保留。"
          action={policy.data ? (
            <SettingsStateSwitch
              checked={policy.data.suggestions_enabled}
              disabled={savePolicy.isPending}
              label={policy.data.suggestions_enabled ? "允许新的成长建议" : "已暂停新的成长建议"}
              onChange={(enabled) => savePolicy.mutate({
                suggestions_enabled: enabled,
                paused_types: policy.data!.paused_types,
              })}
            />
          ) : null}
        />
        {policy.isLoading ? <SettingsInlineNotice>正在读取成长参与设置…</SettingsInlineNotice> : null}
        {policy.data ? (
          <>
            <div className="growth-control-status">
              <SettingsStatusPill tone={policy.data.suggestions_enabled ? "success" : "neutral"}>
                {policy.data.suggestions_enabled ? "正在形成建议" : "已暂停新建议"}
              </SettingsStatusPill>
              <p>已确认的成长不会被自动撤回；你仍可逐条撤回。关系理解继续保持人工确认。</p>
              <span className={`growth-policy-feedback is-${policyFeedback}`} aria-live="polite">
                {policyFeedback === "saving" ? "正在保存…" : policyFeedback === "saved" ? "设置已保存" : policyFeedback === "error" ? "保存失败，已恢复原设置" : ""}
              </span>
            </div>
            <div className="growth-domain-controls" aria-label="按成长领域暂停">
              {GROWTH_DOMAINS.map((domain) => {
                const paused = policy.data!.paused_types.includes(domain.key);
                return <div className="growth-domain-control" key={domain.key}>
                  <span><strong>{domain.label}</strong><small>{domain.description}</small></span>
                  <SettingsStateSwitch
                    checked={!paused}
                    label={!policy.data!.suggestions_enabled ? "总开关暂停" : paused ? "已暂停" : "允许建议"}
                    disabled={savePolicy.isPending || !policy.data!.suggestions_enabled}
                    onChange={(enabled) => savePolicy.mutate({
                      suggestions_enabled: policy.data!.suggestions_enabled,
                      paused_types: enabled
                        ? policy.data!.paused_types.filter((item) => item !== domain.key)
                        : [...policy.data!.paused_types, domain.key],
                    })}
                  />
                </div>;
              })}
            </div>
          </>
        ) : null}
        {policy.isError ? <SettingsInlineNotice tone="danger">暂时无法读取成长参与设置，请刷新后重试。</SettingsInlineNotice> : null}
      </section>

      {companionContext.activeCompanionId ? <RelationshipEvolutionPanel companionId={companionContext.activeCompanionId} /> : null}

      <section className="settings-domain-section" aria-labelledby="growth-records-title">
        <SettingsSectionHeading
          id="growth-records-title"
          icon={Sprout}
          title="已经确认的成长"
          description="这里展示当前伙伴已采用的理解变化。撤回会追加补偿记录，不会改写历史证据。"
        />
        <ListControls
          label="已确认成长筛选"
          query={recordList.query}
          onQueryChange={recordList.setQuery}
          status={recordList.status}
          onStatusChange={recordList.setStatus}
          statuses={recordList.statuses}
          page={recordList.page}
          pageSize={recordList.pageSize}
          total={recordList.total}
          onPageChange={recordList.setPage}
          onPageSizeChange={recordList.setPageSize}
        />
        {recordList.pageItems.length === 0 ? (
          <div className="settings-empty-state"><Sprout size={21} aria-hidden="true" /><strong>还没有已确认的成长</strong><p>确认后的理解变化会在这里形成可回滚的时间线。</p></div>
        ) : (
          <div className="settings-record-list">
            {recordList.pageItems.map((record) => {
              const status = growthStatus(record.status);
              const feedbackKey = `record_${record.id}`;
              return (
                <article key={record.id} className={record.status === "reverted" ? "is-muted" : ""}>
                  <div className="settings-record-heading">
                    <div><small>{growthTypeLabel(record.type)}</small><h3>{record.summary || record.content || "未命名的理解变化"}</h3></div>
                    <SettingsStatusPill tone={status.tone}>{status.label}</SettingsStatusPill>
                  </div>
                  <p>{record.reason || "根据已确认的相处证据形成。"}</p>
                  <div className="settings-record-meta">
                    {record.confidence != null ? <span>确信程度 {Math.round(record.confidence * 100)}%</span> : null}
                    {record.feedback_score != null ? <span>反馈得分 {Math.round(record.feedback_score * 100)}%</span> : null}
                    {(record.downstream_memory_ids?.length ?? 0) > 0 ? <span>关联记忆 {record.downstream_memory_ids!.length} 条</span> : null}
                    {(record.downstream_trace_run_ids?.length ?? 0) > 0 ? <span>关联运行 {record.downstream_trace_run_ids!.length} 条</span> : null}
                  </div>
                  <div className="settings-record-actions">
                    {record.status === "committed" ? (
                      <SettingsAction
                        disabled={Boolean(growth.actionLock[record.id])}
                        onClick={() => growth.revert(record.id)}
                      >
                        <RotateCcw size={14} aria-hidden="true" />{growth.actionLock[record.id] ? "正在撤回…" : "撤回这次成长"}
                      </SettingsAction>
                    ) : null}
                    <SettingsAction
                      variant="quiet"
                      disabled={feedbackState[feedbackKey] === "sent" || feedbackState[feedbackKey] === "sending"}
                      onClick={() => void sendFeedback(record.id, "helpful")}
                    >
                      <ThumbsUp size={14} aria-hidden="true" />{feedbackLabel(feedbackState[feedbackKey], "有帮助")}
                    </SettingsAction>
                  </div>
                  {feedbackState[feedbackKey] === "error" ? <SettingsInlineNotice tone="danger">反馈暂时无法保存，请稍后重试。</SettingsInlineNotice> : null}
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="settings-domain-section" aria-labelledby="growth-candidates-title">
        <SettingsSectionHeading
          id="growth-candidates-title"
          icon={Sparkles}
          title="候选与影响预览"
          description="先理解它准备改变什么，再决定是否采用。技术枚举和原始引用收在高级证据中。"
        />
        <ListControls
          label="成长候选筛选"
          query={candidateList.query}
          onQueryChange={candidateList.setQuery}
          status={candidateList.status}
          onStatusChange={candidateList.setStatus}
          statuses={candidateList.statuses}
          page={candidateList.page}
          pageSize={candidateList.pageSize}
          total={candidateList.total}
          onPageChange={candidateList.setPage}
          onPageSizeChange={candidateList.setPageSize}
        />
        {candidateList.pageItems.length === 0 ? (
          <div className="settings-empty-state"><Sparkles size={21} aria-hidden="true" /><strong>当前没有成长候选</strong><p>新的纠错或理解建议会先进入这里，而不是自动应用。</p></div>
        ) : (
          <div className="settings-record-list">
            {candidateList.pageItems.map((candidate) => {
              const feedbackKey = `candidate_${candidate.id}`;
              const status = growthStatus(candidate.status);
              const impact = candidate.impact_preview_json as Record<string, unknown> | null | undefined;
              return (
                <article key={candidate.id}>
                  <div className="settings-record-heading">
                    <div><small>{growthTypeLabel(candidate.type)}</small><h3>{candidate.content || candidate.reason || "未命名的成长候选"}</h3></div>
                    <SettingsStatusPill tone={status.tone}>{status.label}</SettingsStatusPill>
                  </div>
                  {candidate.reason && candidate.content !== candidate.reason ? <p>{candidate.reason}</p> : null}
                  <div className="settings-record-meta">
                    {candidate.evidence_score != null ? <span>证据程度 {Math.round(candidate.evidence_score * 100)}%</span> : null}
                    {candidate.feedback_score != null ? <span>反馈得分 {Math.round(candidate.feedback_score * 100)}%</span> : null}
                    {candidate.risk_level ? <span>风险 {riskLabel(candidate.risk_level)}</span> : null}
                    {(candidate.evidence_memory_ids?.length ?? 0) > 0 ? <span>关联证据 {candidate.evidence_memory_ids!.length} 条</span> : null}
                  </div>
                  {impact && Object.keys(impact).length > 0 ? (
                    <details className="settings-evidence-disclosure">
                      <summary>查看影响与技术证据</summary>
                      <pre>{JSON.stringify(impact, null, 2)}</pre>
                    </details>
                  ) : <p className="settings-record-note"><AlertCircle size={14} aria-hidden="true" />尚未记录独立影响预览，确认前不会自动应用。</p>}
                  <div className="settings-record-actions">
                    {candidate.status === "pending" || candidate.status === "candidate" ? (
                      <>
                        <SettingsAction variant="primary" disabled={Boolean(growth.actionLock[candidate.id])} onClick={() => growth.commit(candidate.id)}>确认成长</SettingsAction>
                        <SettingsAction
                          disabled={Boolean(growth.actionLock[candidate.id])}
                          onClick={() => { setEditingCandidate(candidate); setEditedContent(candidate.content || ""); }}
                        >
                          修改后确认
                        </SettingsAction>
                        <SettingsAction disabled={Boolean(growth.actionLock[candidate.id])} onClick={() => growth.reject(candidate.id)}>不采用</SettingsAction>
                      </>
                    ) : null}
                    <SettingsAction variant="quiet" disabled={feedbackState[feedbackKey] === "sent" || feedbackState[feedbackKey] === "sending"} onClick={() => void sendFeedback(candidate.id, "helpful")}><ThumbsUp size={14} aria-hidden="true" />{feedbackLabel(feedbackState[feedbackKey], "有帮助")}</SettingsAction>
                    <SettingsAction variant="quiet" disabled={feedbackState[feedbackKey] === "sent" || feedbackState[feedbackKey] === "sending"} onClick={() => void sendFeedback(candidate.id, "wrong")}><ThumbsDown size={14} aria-hidden="true" />{feedbackLabel(feedbackState[feedbackKey], "不准确")}</SettingsAction>
                  </div>
                  {feedbackState[feedbackKey] === "error" ? <SettingsInlineNotice tone="danger">反馈暂时无法保存，请稍后重试。</SettingsInlineNotice> : null}
                </article>
              );
            })}
          </div>
        )}
      </section>
      {editingCandidate ? (
        <section className="growth-edit-panel" role="dialog" aria-modal="true" aria-labelledby="growth-edit-title">
          <div>
            <small>修改成长理解</small>
            <h2 id="growth-edit-title">让这项变化更符合你的真实感受</h2>
            <p>修改只调整这项理解的表述；原始证据、风险判断和影响范围仍保留，确认后形成新的成长记录。</p>
            <textarea
              value={editedContent}
              onChange={(event) => setEditedContent(event.target.value)}
              maxLength={3000}
              aria-label="修改后的成长理解"
            />
            <div>
              <SettingsAction
                variant="primary"
                disabled={!editedContent.trim() || editedContent.trim() === editingCandidate.content || Boolean(growth.actionLock[editingCandidate.id])}
                onClick={async () => {
                  const saved = await growth.editAndCommit(editingCandidate.id, editedContent.trim());
                  if (saved) setEditingCandidate(null);
                }}
              >
                {growth.actionLock[editingCandidate.id] ? "正在确认…" : "保存并确认成长"}
              </SettingsAction>
              <SettingsAction onClick={() => setEditingCandidate(null)}>取消</SettingsAction>
            </div>
          </div>
        </section>
      ) : null}
    </main>
  );
}

function feedbackLabel(state: FeedbackState | undefined, idle: string) {
  if (state === "sent") return "已记录";
  if (state === "sending") return "正在记录…";
  return idle;
}

function growthTypeLabel(value?: string | null) {
  return ({
    understanding_update: "理解变化",
    preference: "偏好理解",
    relationship: "关系理解",
    correction: "纠错",
    behavior: "互动方式",
  } as Record<string, string>)[value ?? ""] ?? "成长理解";
}

function riskLabel(value: string) {
  return ({ low: "低", medium: "中", high: "高", critical: "关键" } as Record<string, string>)[value] ?? "待核对";
}

function growthStatus(value: string): { label: string; tone: "neutral" | "info" | "success" | "warning" | "danger" } {
  return ({
    pending: { label: "待确认", tone: "warning" },
    candidate: { label: "待确认", tone: "warning" },
    committed: { label: "已确认", tone: "success" },
    reverted: { label: "已撤回", tone: "neutral" },
    rejected: { label: "已拒绝", tone: "neutral" },
    corrected: { label: "已纠正", tone: "info" },
    failed: { label: "失败", tone: "danger" },
  } as Record<string, { label: string; tone: "neutral" | "info" | "success" | "warning" | "danger" }>)[value] ?? { label: "已记录", tone: "neutral" };
}
