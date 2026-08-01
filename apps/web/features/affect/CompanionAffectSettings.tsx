"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleGauge, RotateCcw, ShieldCheck, Waves } from "lucide-react";
import { SettingsSegmentedControl, SettingsStateSwitch } from "@/components/settings/SettingsControls";
import { affectApi, type AffectState } from "@/lib/api/affect";
import styles from "./CompanionAffectSettings.module.css";

const intensityLabels: Record<AffectState["expression_intensity"], string> = {
  off: "不表达", subtle: "轻微流露", balanced: "自然表达",
};

export function CompanionAffectSettings({ companionId }: { companionId: string }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const stateKey = ["affect", companionId, "state"] as const;
  const stateQuery = useQuery({ queryKey: stateKey, queryFn: () => affectApi.state(companionId) });
  const eventsQuery = useQuery({ queryKey: ["affect", companionId, "events"], queryFn: () => affectApi.events(companionId) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["affect", companionId] });
  const preferences = useMutation({
    mutationFn: ({ expectedRevision, enabled, intensity }: { expectedRevision: number; enabled: boolean; intensity: AffectState["expression_intensity"] }) => affectApi.preferences(companionId, expectedRevision, enabled, intensity),
    onMutate: async ({ enabled, intensity }) => {
      setError(null);
      await queryClient.cancelQueries({ queryKey: stateKey });
      const previous = queryClient.getQueryData<AffectState | null>(stateKey);
      queryClient.setQueryData<AffectState | null>(stateKey, (current) => current ? {
        ...current,
        expression_enabled: enabled,
        expression_intensity: enabled ? intensity : "off",
      } : current);
      return { previous };
    },
    onSuccess: (nextState) => queryClient.setQueryData(stateKey, nextState),
    onError: (value, _variables, context) => {
      queryClient.setQueryData(stateKey, context?.previous);
      setError(value instanceof Error ? value.message : "暂时无法保存表达偏好");
    },
  });
  const correction = useMutation({
    mutationFn: ({ id, revision }: { id: string; revision: number }) => affectApi.correct(companionId, id, revision),
    onMutate: () => setError(null), onSuccess: refresh,
    onError: (value) => setError(value instanceof Error ? value.message : "暂时无法纠正事件理解"),
  });

  if (stateQuery.isLoading || eventsQuery.isLoading) return <main className={styles.affectSettings}><p className={styles.affectStatus}>正在读取伙伴的表达状态…</p></main>;
  if (stateQuery.isError || eventsQuery.isError) return <main className={styles.affectSettings}><p className={styles.affectStatus} role="alert">暂时无法读取表达状态，请稍后重试。</p></main>;
  const state = stateQuery.data;
  const events = eventsQuery.data?.items ?? [];
  const current = events.find((event) => event.id === state?.current_event_id && event.operation === "appraised");
  const expressionEnabled = state?.expression_enabled ?? true;
  const expressionIntensity = state?.expression_intensity === "balanced" ? "balanced" : "subtle";
  const savePreferences = (enabled: boolean, intensity: AffectState["expression_intensity"]) => {
    if (preferences.isPending) return;
    preferences.mutate({ expectedRevision: state?.revision ?? 0, enabled, intensity });
  };

  return <main className={styles.affectSettings}>
    <header className={styles.affectHero}><p>COMPANION AFFECT</p><h1>相处中的表达余韵</h1><span>这是伙伴用于保持语气连续的模拟表达状态，不代表意识、真实感受或依恋，也不会越过你的边界与安静时段。</span></header>
    <section className={styles.affectCurrent} aria-labelledby="affect-current-title">
      <div><Waves size={21} aria-hidden="true" /><p>当前有限表达</p><h2 id="affect-current-title">{state?.expression.label ?? "平稳"}</h2><span>{state ? `${toneLabel(state.expression.tone)} · ${focusLabel(state.expression.focus)}` : "尚无已验证事件，保持中性基线"}</span></div>
      <aside><ShieldCheck size={17} aria-hidden="true" /><strong>边界始终优先</strong><p>Hard stop、revoke、quiet/focus、meaningful silence 与其他边界不会被表达状态覆盖。</p></aside>
    </section>
    <section className={styles.affectSection} aria-labelledby="affect-preference-title">
      <div className={styles.affectSectionHeading}><div><CircleGauge size={19} aria-hidden="true" /><h2 id="affect-preference-title">表达偏好</h2></div><p>你控制能否流露以及流露程度，但不直接操纵内部数值。</p></div>
      <div className={styles.affectPreferences}>
        <div className={styles.affectSwitchRow}><span>允许表达余韵</span><SettingsStateSwitch checked={expressionEnabled} onChange={(enabled) => savePreferences(enabled, enabled ? expressionIntensity : "off")} /></div>
        <fieldset disabled={!expressionEnabled}><legend>表达程度</legend><SettingsSegmentedControl label="表达程度" value={expressionIntensity} disabled={!expressionEnabled} options={(["subtle", "balanced"] as const).map((value) => ({ value, label: intensityLabels[value] }))} onChange={(value) => savePreferences(true, value)} /></fieldset>
      </div>
      <p className={styles.affectPreferenceStatus} aria-live="polite">{preferences.isPending ? "正在保存表达偏好…" : preferences.isSuccess ? "表达偏好已保存" : ""}</p>
    </section>
    <section className={styles.affectSection} aria-labelledby="affect-events-title">
      <div className={styles.affectSectionHeading}><div><Waves size={19} aria-hidden="true" /><h2 id="affect-events-title">互动理解</h2></div><p>只展示有限摘要与用户原话证据；纠错会追加补偿事件，不改写历史。</p></div>
      {events.length === 0 ? <p className={styles.affectEmpty}>尚无通过证据校验的互动理解。</p> : <ol className={styles.affectEvents}>{events.map((event) => <li key={event.id} data-status={event.status}><div><span>{event.status === "invalidated" ? "已纠正" : event.operation === "corrected" ? "补偿记录" : "已采用"}</span><time>{event.created_at ? new Date(event.created_at).toLocaleString("zh-CN") : ""}</time></div><h3>{event.summary}</h3>{event.evidence_quote ? <blockquote>“{event.evidence_quote}”</blockquote> : null}{current?.id === event.id && state ? <button type="button" disabled={correction.isPending} onClick={() => correction.mutate({ id: event.id, revision: state.revision })}><RotateCcw size={14} aria-hidden="true" />这次理解不准确</button> : null}</li>)}</ol>}
    </section>
    {error ? <p className={styles.affectError} role="alert">{error}。若页面已打开较久，请刷新后重试。</p> : null}
  </main>;
}

function toneLabel(value: string) { return ({ steady: "语气平稳", bright: "语气明亮", warm: "语气温和", careful: "语气谨慎", subdued: "语气克制", focused: "语气专注" } as Record<string, string>)[value] ?? "语气平稳"; }
function focusLabel(value: string) { return ({ balanced: "关注均衡", engaged: "更投入当前话题", reassuring: "倾向安稳回应", clarify: "优先澄清", reflective: "倾向安静反思", current_task: "聚焦当前任务" } as Record<string, string>)[value] ?? "关注当前对话"; }
