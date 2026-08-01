"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, RotateCcw, ShieldCheck } from "lucide-react";
import { ConfirmActionDialog } from "@/components/patterns/ConfirmActionDialog";
import { SettingsSegmentedControl } from "@/components/settings/SettingsControls";
import {
  getPresenceTimingPolicy,
  rollbackPresenceTimingPolicy,
  updatePresenceTimingPolicy,
  type PresencePolicySurface,
} from "@/lib/api/settings";

export function PresenceTimingPolicyPanel({
  companionId,
}: {
  companionId?: string | null;
}) {
  const [surface, setSurface] = useState<PresencePolicySurface>("queue");
  const [confirmAssistive, setConfirmAssistive] = useState(false);
  const client = useQueryClient();
  const key = ["presence-timing-policy", companionId, surface];
  const query = useQuery({
    queryKey: key,
    queryFn: () => getPresenceTimingPolicy(companionId!, surface),
    enabled: Boolean(companionId),
  });
  const update = useMutation({
    mutationFn: (enabled: boolean) =>
      updatePresenceTimingPolicy(
        companionId!,
        surface,
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
      rollbackPresenceTimingPolicy(
        companionId!,
        surface,
        query.data?.revision ?? 0,
      ),
    onSuccess: (value) => client.setQueryData(key, value),
    onError: () => void query.refetch(),
  });

  if (!companionId) return null;
  return (
    <section className="memory-policy" aria-labelledby="presence-policy-title">
      <header>
        <div>
          <small>主动陪伴节奏</small>
          <h2 id="presence-policy-title">伙伴怎样判断何时出现</h2>
          <p>
            为当前伙伴和所选场景选择稳定节奏，或在证据充分时启用辅助判断。它只能保持或降低打扰，
            不能越过 hard stop、quiet/focus、meaningful silence 或渠道边界。
          </p>
        </div>
        <span><ShieldCheck size={16} />不会随机主动打扰</span>
      </header>
      <label className="presence-policy-surface">
        <span>生效场景</span>
        <select
          value={surface}
          onChange={(event) =>
            setSurface(event.target.value as PresencePolicySurface)
          }
          disabled={update.isPending || rollback.isPending}
        >
          <option value="queue">稍后出现／低打扰</option>
          <option value="hub">伙伴首页／当下建议</option>
        </select>
      </label>
      {query.isLoading ? <p>正在读取当前范围的准入证据…</p> : null}
      {query.isError ? <p role="alert">暂时无法读取 Presence Policy 状态。</p> : null}
      {query.data ? (
        <>
          <div className="memory-policy-grid">
            <article><span>当前方式</span><strong>{label(query.data.status)}</strong></article>
            <article><span>辅助模式条件</span><strong>{label(query.data.readiness.readiness_status)}</strong></article>
            <article><span>节奏模型</span><strong>{query.data.readiness.shadow_policy_ready ? "已准备" : "尚未准备"}</strong></article>
            <article><span>可撤回</span><strong>{query.data.rollback_available ? "是" : "暂无变更"}</strong></article>
          </div>
          {query.data.block_reason ? (
            <p className="memory-policy-block">
              <CircleAlert size={16} />当前无法启用：{query.data.block_reason}
            </p>
          ) : null}
          <div className="learned-policy-control">
            <SettingsSegmentedControl
              label="主动陪伴判断方式"
              value={query.data.status === "assistive" ? "assistive" : "shadow"}
              disabled={update.isPending || rollback.isPending}
              options={[
                { value: "shadow", label: "稳定模式" },
                { value: "assistive", label: "辅助模式", disabled: !query.data.readiness.eligible },
                { value: "active", label: "主动模式", disabled: true },
              ]}
              onChange={(mode) => mode === "shadow" ? update.mutate(false) : mode === "assistive" ? setConfirmAssistive(true) : undefined}
            />
            <p>主动模式需要独立授权和真实陪伴效果验收，当前公开版本不可启用。</p>
          </div>
          <div className="memory-policy-actions">
            <button
              type="button"
              disabled={
                !query.data.rollback_available ||
                update.isPending ||
                rollback.isPending
              }
              onClick={() => rollback.mutate()}
            >
              <RotateCcw size={15} />撤回上一次方式调整
            </button>
          </div>
          <p className="memory-policy-footnote">
            不进行随机主动打扰，不直接控制 Discord 外发，
            不共享其他伙伴的样本或权重。
          </p>
          {update.isError || rollback.isError ? (
            <p role="alert">操作未生效，已重新读取最新状态。</p>
          ) : null}
        </>
      ) : null}
      {confirmAssistive ? <ConfirmActionDialog
        title="为这个场景启用辅助节奏判断？"
        description="系统只会在准入条件满足时参考辅助建议，并且只能保持或减少打扰；安静时段、专注模式、停止与撤销始终优先。"
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
    passed: "条件已满足",
    not_evaluated: "尚未评测",
  } as Record<string, string>)[value] ?? value;
}
