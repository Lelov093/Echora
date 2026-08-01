"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, RotateCcw, ShieldCheck } from "lucide-react";
import { ConfirmActionDialog } from "@/components/patterns/ConfirmActionDialog";
import { SettingsSegmentedControl } from "@/components/settings/SettingsControls";
import {
  getMemorySelectionPolicy,
  rollbackMemorySelectionPolicy,
  updateMemorySelectionPolicy,
} from "@/lib/api/settings";

export function MemorySelectionPolicyPanel({
  companionId,
}: {
  companionId?: string | null;
}) {
  const client = useQueryClient();
  const [confirmAssistive, setConfirmAssistive] = useState(false);
  const key = ["memory-selection-policy", companionId];
  const query = useQuery({
    queryKey: key,
    queryFn: () => getMemorySelectionPolicy(companionId!),
    enabled: Boolean(companionId),
  });
  const update = useMutation({
    mutationFn: (enabled: boolean) =>
      updateMemorySelectionPolicy(
        companionId!,
        enabled,
        query.data?.revision ?? 0,
      ),
    onSuccess: (value) => {
      client.setQueryData(key, value);
      setConfirmAssistive(false);
    },
    onError: () => void query.refetch(),
  });
  const rollback = useMutation({
    mutationFn: () =>
      rollbackMemorySelectionPolicy(
        companionId!,
        query.data?.revision ?? 0,
      ),
    onSuccess: (value) => client.setQueryData(key, value),
    onError: () => void query.refetch(),
  });

  if (!companionId) return null;
  return (
    <section className="memory-policy" aria-labelledby="memory-policy-title">
      <header>
        <div>
          <small>记忆调用方式</small>
          <h2 id="memory-policy-title">伙伴怎样选择相关记忆</h2>
          <p>
            为当前伙伴选择稳定排序，或在证据充分时让智能排序辅助选择。边界过滤始终先执行；
            证据不足、模型变化或异常会立即退回稳定排序。
          </p>
        </div>
        <span><ShieldCheck size={16} />默认保持稳定模式</span>
      </header>
      {query.isLoading ? <p>正在读取当前伙伴的准入证据…</p> : null}
      {query.isError ? <p role="alert">暂时无法读取 Policy 状态。</p> : null}
      {query.data ? (
        <>
          <div className="memory-policy-grid">
            <article><span>当前方式</span><strong>{label(query.data.status)}</strong></article>
            <article><span>辅助模式条件</span><strong>{label(query.data.readiness.readiness_status)}</strong></article>
            <article><span>排序模型</span><strong>{query.data.readiness.model_ready ? "已准备" : "尚未准备"}</strong></article>
            <article><span>可撤回</span><strong>{query.data.rollback_available ? "是" : "暂无变更"}</strong></article>
          </div>
          {query.data.block_reason ? (
            <p className="memory-policy-block"><CircleAlert size={16} />当前无法启用：{query.data.block_reason}</p>
          ) : null}
          <div className="learned-policy-control">
            <SettingsSegmentedControl
              label="记忆排序参与程度"
              value={query.data.status === "assistive" ? "assistive" : "shadow"}
              disabled={update.isPending || rollback.isPending}
              options={[
                { value: "shadow", label: "稳定模式" },
                { value: "assistive", label: "辅助模式", disabled: !query.data.readiness.eligible },
                { value: "active", label: "主动模式", disabled: true },
              ]}
              onChange={(mode) => mode === "shadow" ? update.mutate(false) : mode === "assistive" ? setConfirmAssistive(true) : undefined}
            />
            <p>主动模式需要独立授权、完整评测与回滚验收，当前公开版本不可启用。</p>
          </div>
          <div className="memory-policy-actions">
            <button
              type="button"
              disabled={!query.data.rollback_available || update.isPending || rollback.isPending}
              onClick={() => rollback.mutate()}
            >
              <RotateCcw size={15} />撤回上一次方式调整
            </button>
          </div>
          <p className="memory-policy-footnote">
            每位伙伴独立设置，不共享其他伙伴的样本或权重；整体自动化设置不能代替你的明确选择。
          </p>
          {update.isError || rollback.isError ? (
            <p role="alert">操作未生效，已重新读取最新状态。</p>
          ) : null}
        </>
      ) : null}
      {confirmAssistive ? <ConfirmActionDialog
        title="为当前伙伴启用辅助记忆排序？"
        description="系统会参考已通过准入检查的排序建议，但仍先执行隐私、敏感内容与 Companion 隔离过滤；异常时自动回退稳定模式。"
        confirmLabel="确认启用辅助模式"
        cancelLabel="保持稳定模式"
        busy={update.isPending}
        onCancel={() => setConfirmAssistive(false)}
        onConfirm={() => update.mutate(true)}
      /> : null}
    </section>
  );
}

function label(value: string) {
  return ({
    shadow: "稳定模式",
    assistive: "辅助模式",
    heuristic_fallback: "已回退启发式",
    insufficient_data: "数据不足",
    failed: "评测未通过",
    ready_for_assistive_review: "条件已满足",
    not_evaluated: "尚未评测",
  } as Record<string, string>)[value] ?? value;
}
