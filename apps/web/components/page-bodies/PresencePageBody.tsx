"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BellRing,
  CalendarClock,
  Check,
  Clock3,
  MessageCircle,
  Moon,
  Plus,
  Radio,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { createConversation, listConversations, type ConversationBrief } from "@/lib/api/conversations";
import {
  getPresenceConfiguration,
  listPresenceOccurrences,
  savePresenceConfiguration,
  triggerPresenceSchedule,
  type PresenceConfiguration,
  type PresenceConfigurationValue,
  type PresenceOccurrence,
} from "@/lib/api/presence";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";
import { usePresenceQueue } from "@/lib/hooks/usePresenceQueue";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
const PROACTIVE_LEVELS = [
  { value: "low" as const, label: "克制", detail: "只保留真正重要、低打扰的联系机会" },
  { value: "medium" as const, label: "自然", detail: "在有意义的时机自然出现" },
  { value: "high" as const, label: "积极", detail: "更主动分享，但仍服从全部边界" },
];
const PRESENCE_STYLES = [
  { value: "quiet" as const, label: "轻声陪伴", detail: "表达简短、克制，尽量不打断当前节奏" },
  { value: "balanced" as const, label: "自然接续", detail: "温和、有上下文，在亲近和留白之间平衡" },
  { value: "expressive" as const, label: "更有表达", detail: "允许更鲜明的语气，但不提高联系频率" },
];
const NOTIFICATION_SURFACES = [
  { value: "hub_queue_only" as const, label: "只在对话中出现" },
  { value: "allow_light_notification" as const, label: "允许轻提醒" },
  { value: "disabled" as const, label: "不额外提醒" },
];

function minuteToTime(value: number) {
  const minute = ((value % 1440) + 1440) % 1440;
  return `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;
}

function timeToMinute(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function formatDate(value?: string | null) {
  if (!value) return "尚未安排";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function readableReason(value?: string | null) {
  const labels: Record<string, string> = {
    min_interval: "仍在问候间隔内",
    quiet_hours: "当前处于安静时段",
    boundary_quiet_hours: "伙伴边界要求保持安静",
    profile_quiet_hours: "伙伴档案边界要求保持安静",
    focus_mode: "Focus mode 正在生效",
    hard_stop: "Hard stop 正在生效",
    proactive_presence_disabled: "主动联系已关闭",
    interrupt_policy_user_initiated_only: "当前只回应你主动发起的对话",
    daily_presence_limit: "今天的联系预算已用完",
    schedule_reconfigured: "计划更新后已重新安排",
  };
  return value ? labels[value] ?? value : "等待运行";
}

export default function PresencePageBody() {
  const companion = useActiveCompanionContext();
  const queue = usePresenceQueue(companion.companionFilterId, companion.hydrated);
  const [configuration, setConfiguration] = useState<PresenceConfiguration | null>(null);
  const [draft, setDraft] = useState<PresenceConfigurationValue | null>(null);
  const [conversations, setConversations] = useState<ConversationBrief[]>([]);
  const [occurrences, setOccurrences] = useState<PresenceOccurrence[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error" | "info"; text: string } | null>(null);
  const userId = companion.activeCompanion?.user_id;
  const companionId = companion.activeCompanionId;

  const load = useCallback(async () => {
    if (!companion.hydrated || !userId || !companionId) return;
    setLoading(true);
    setNotice(null);
    try {
      const [configurationValue, conversationPage, occurrenceRows] = await Promise.all([
        getPresenceConfiguration(companionId, userId),
        listConversations({ companion_id: companionId, status: "active", page: 1, page_size: 100 }),
        listPresenceOccurrences(companionId, userId),
      ]);
      const nextDraft = { ...configurationValue.configuration };
      if (!configurationValue.versions.schedule_revision && nextDraft.timezone === "UTC") {
        nextDraft.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai";
      }
      setConfiguration(configurationValue);
      setDraft(nextDraft);
      setConversations(conversationPage.items ?? []);
      setOccurrences(occurrenceRows);
      if (configurationValue.consistency.status === "needs_save_to_align") {
        setNotice({ kind: "info", text: "检测到旧配置之间存在差异。确认当前选择并保存后，它们会通过同一事务重新对齐。" });
      }
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "暂时无法读取 Presence 设置。" });
    } finally {
      setLoading(false);
    }
  }, [companion.hydrated, companionId, userId]);

  /* eslint-disable react-hooks/set-state-in-effect -- Companion-scoped API state loads after hydration. */
  useEffect(() => { void load(); }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const dirty = useMemo(() => {
    if (!configuration || !draft) return false;
    return JSON.stringify(draft) !== JSON.stringify(configuration.configuration);
  }, [configuration, draft]);
  const boundConversation = useMemo(
    () => conversations.find((item) => item.id === draft?.bound_conversation_id),
    [conversations, draft?.bound_conversation_id],
  );

  const updateDraft = <K extends keyof PresenceConfigurationValue>(key: K, value: PresenceConfigurationValue[K]) => {
    setDraft((current) => current ? { ...current, [key]: value } : current);
  };

  const validate = () => {
    if (!draft) return "Presence 设置尚未读取完成。";
    if (draft.enabled && draft.destination_mode === "bound_conversation" && !draft.bound_conversation_id) {
      return "启用主动联系前，请先选择或新建一个绑定对话。";
    }
    if (draft.weekdays.length === 0) return "请至少选择一个可联系日期。";
    if (draft.timing_mode === "random_window" && draft.window_start_minute === draft.window_end_minute) {
      return "随机发送时段需要包含至少一分钟。";
    }
    if (draft.cadence_mode === "random_interval" && draft.random_interval_max_minutes < draft.random_interval_min_minutes) {
      return "随机间隔的最大值不能小于最小值。";
    }
    if (draft.quiet_hours.enabled && draft.quiet_hours.start === draft.quiet_hours.end) {
      return "安静时段的开始和结束不能相同。";
    }
    return null;
  };

  const save = async () => {
    if (!userId || !companionId || !configuration || !draft) return;
    const error = validate();
    if (error) {
      setNotice({ kind: "error", text: error });
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      const saved = await savePresenceConfiguration(companionId, userId, {
        ...draft,
        expected_schedule_revision: configuration.versions.schedule_revision,
        expected_policy_updated_at: configuration.versions.policy_updated_at,
        expected_persona_updated_at: configuration.versions.persona_updated_at,
        expected_boundary_updated_at: configuration.versions.boundary_updated_at,
      });
      setConfiguration(saved);
      setDraft({ ...saved.configuration });
      setOccurrences(await listPresenceOccurrences(companionId, userId));
      setNotice({
        kind: "ok",
        text: saved.configuration.enabled
          ? "Presence 设置已完整保存，下一次联系时间和全部边界已对齐。"
          : "设置已保存。伙伴会保留当前节奏，但只回应你主动发起的对话。",
      });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "保存失败；所有设置均保持原状。" });
    } finally {
      setSaving(false);
    }
  };

  const createAndBind = async () => {
    if (!userId || !companionId) return;
    setCreating(true);
    setNotice(null);
    try {
      const created = await createConversation({
        user_id: userId,
        companion_id: companionId,
        title: "伙伴的主动问候",
        mode_key: "companion",
      });
      setConversations((items) => [created, ...items]);
      setDraft((current) => current ? { ...current, destination_mode: "bound_conversation", bound_conversation_id: created.id } : current);
      setNotice({ kind: "info", text: "已新建空对话并选中；保存 Presence 设置后才会正式绑定。" });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "无法新建对话。" });
    } finally {
      setCreating(false);
    }
  };

  const trigger = async () => {
    const revision = configuration?.versions.schedule_revision;
    if (!userId || !companionId || !configuration?.configuration.enabled || !revision || dirty) return;
    setTriggering(true);
    setNotice(null);
    try {
      const result = await triggerPresenceSchedule(companionId, userId, revision);
      setOccurrences(await listPresenceOccurrences(companionId, userId));
      await queue.reload();
      const reason = result.suppression_reason || result.error_code || result.status;
      setNotice({
        kind: result.status === "delivered" ? "ok" : "info",
        text: result.status === "delivered"
          ? "测试问候已发送到绑定对话。"
          : result.status === "retry_wait"
            ? `真实模型暂时未完成，系统已保留原计划等待重试：${readableReason(reason)}`
            : `本次保持安静：${readableReason(reason)}`,
      });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "测试发送失败。" });
    } finally {
      setTriggering(false);
    }
  };

  if (loading) return <div className="page-load">正在读取伙伴的 Presence 节奏……</div>;
  if (!draft || !configuration) {
    return <section className="presence-policy-state is-error"><p>{notice?.text || "Presence 设置暂时不可用。"}</p><button type="button" className="presence-secondary-action presence-interactive" onClick={() => void load()}>重新读取</button></section>;
  }

  return (
    <div className="presence-settings-flow">
      <section className="presence-schedule-hero" aria-labelledby="presence-switch-title">
        <div>
          <span className="presence-kicker"><Radio size={15} /> 主动联系</span>
          <h2 id="presence-switch-title">让伙伴在合适的时候来找你</h2>
          <p>关闭后只回应你主动发起的对话；开启时仍会逐次检查 Hard stop、安静时段、Focus mode 与 meaningful silence。</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={draft.enabled}
          aria-label="允许伙伴主动联系"
          className={`presence-master-switch presence-interactive ${draft.enabled ? "is-on" : ""}`}
          onClick={() => updateDraft("enabled", !draft.enabled)}
        >
          <span aria-hidden="true" />{draft.enabled ? "已启用" : "仅回应"}
        </button>
      </section>

      {notice ? <div className={`presence-notice is-${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}>{notice.text}</div> : null}

      <section className="presence-setting-section" aria-labelledby="presence-rhythm-title">
        <div className="presence-section-heading"><Sparkles size={19} /><div><h3 id="presence-rhythm-title">联系的节奏与表达</h3><p>“多久出现”和“如何表达”是两个独立维度；更有表达不会自动增加联系频率。</p></div></div>
        <fieldset className="presence-choice-fieldset">
          <legend>主动频率</legend>
          <div className="presence-choice-grid is-three">
            {PROACTIVE_LEVELS.map((option) => <button key={option.value} type="button" aria-pressed={draft.proactive_level === option.value} className={`presence-interactive ${draft.proactive_level === option.value ? "is-selected" : ""}`} onClick={() => updateDraft("proactive_level", option.value)}><span><strong>{option.label}</strong><small>{option.detail}</small></span>{draft.proactive_level === option.value ? <Check size={18} /> : null}</button>)}
          </div>
        </fieldset>
        <fieldset className="presence-choice-fieldset">
          <legend>表达方式</legend>
          <div className="presence-choice-grid is-three">
            {PRESENCE_STYLES.map((option) => <button key={option.value} type="button" aria-pressed={draft.presence_style === option.value} className={`presence-interactive ${draft.presence_style === option.value ? "is-selected" : ""}`} onClick={() => updateDraft("presence_style", option.value)}><span><strong>{option.label}</strong><small>{option.detail}</small></span>{draft.presence_style === option.value ? <Check size={18} /> : null}</button>)}
          </div>
        </fieldset>
        <div className="presence-switch-card">
          <span><strong>Meaningful silence</strong><small>没有足够意义时保持安静，不为活跃而制造提示。</small></span>
          <button type="button" role="switch" aria-checked={draft.meaningful_silence_enabled} className={`presence-master-switch presence-interactive ${draft.meaningful_silence_enabled ? "is-on" : ""}`} onClick={() => updateDraft("meaningful_silence_enabled", !draft.meaningful_silence_enabled)}><span aria-hidden="true" />{draft.meaningful_silence_enabled ? "已启用" : "已关闭"}</button>
        </div>
      </section>

      <section className="presence-setting-section" aria-labelledby="presence-destination-title">
        <div className="presence-section-heading"><MessageCircle size={19} /><div><h3 id="presence-destination-title">出现位置与提醒方式</h3><p>先决定问候进入哪个对话，再决定是否需要对话之外的轻提醒。</p></div></div>
        <div className="presence-choice-grid">
          <button type="button" aria-pressed={draft.destination_mode === "bound_conversation"} className={`presence-interactive ${draft.destination_mode === "bound_conversation" ? "is-selected" : ""}`} onClick={() => updateDraft("destination_mode", "bound_conversation")}><span><strong>自定义</strong><small>持续写入你指定的一个对话</small></span>{draft.destination_mode === "bound_conversation" ? <Check size={18} /> : null}</button>
          <button type="button" aria-pressed={draft.destination_mode === "new_conversation_per_delivery"} className={`presence-interactive ${draft.destination_mode === "new_conversation_per_delivery" ? "is-selected" : ""}`} onClick={() => setDraft((current) => current ? { ...current, destination_mode: "new_conversation_per_delivery", bound_conversation_id: null } : current)}><span><strong>每次新建</strong><small>每条成功问候拥有独立上下文</small></span>{draft.destination_mode === "new_conversation_per_delivery" ? <Check size={18} /> : null}</button>
        </div>
        {draft.destination_mode === "bound_conversation" ? <div className="presence-bound-row"><label><span>所绑定的对话</span><select value={draft.bound_conversation_id ?? ""} onChange={(event) => updateDraft("bound_conversation_id", event.target.value || null)}><option value="">选择一个活跃对话</option>{conversations.map((item) => <option key={item.id} value={item.id}>{item.title || "未命名对话"}</option>)}</select></label><button type="button" className="presence-secondary-action presence-interactive" disabled={creating} onClick={createAndBind}><Plus size={16} />{creating ? "正在新建…" : "新建并选择"}</button></div> : <p className="presence-inline-note">发送成功后才创建对话；被边界拦截或模型失败时不会留下空对话。</p>}
        {boundConversation ? <p className="presence-inline-note"><Check size={14} /> 当前选择：{boundConversation.title}</p> : null}
        <fieldset className="presence-inline-fieldset"><legend><BellRing size={15} /> 提醒方式</legend><div className="presence-segmented is-three">{NOTIFICATION_SURFACES.map((option) => <button key={option.value} type="button" aria-pressed={draft.notification_surface === option.value} className={`presence-interactive ${draft.notification_surface === option.value ? "is-selected" : ""}`} onClick={() => updateDraft("notification_surface", option.value)}>{option.label}</button>)}</div></fieldset>
      </section>

      <section className="presence-setting-section" aria-labelledby="presence-time-title">
        <div className="presence-section-heading"><CalendarClock size={19} /><div><h3 id="presence-time-title">时间、频率与安静边界</h3><p>这里是唯一的 Presence 时间配置。随机选点落库后不会因重启或重试重新抽取。</p></div></div>
        <div className="presence-time-grid">
          <fieldset><legend>发送时间</legend><div className="presence-segmented"><button type="button" aria-pressed={draft.timing_mode === "fixed"} className={`presence-interactive ${draft.timing_mode === "fixed" ? "is-selected" : ""}`} onClick={() => updateDraft("timing_mode", "fixed")}>固定时间</button><button type="button" aria-pressed={draft.timing_mode === "random_window"} className={`presence-interactive ${draft.timing_mode === "random_window" ? "is-selected" : ""}`} onClick={() => updateDraft("timing_mode", "random_window")}>时段内随机</button></div>{draft.timing_mode === "fixed" ? <label><span>每天</span><input type="time" value={minuteToTime(draft.fixed_minute_of_day)} onChange={(event) => updateDraft("fixed_minute_of_day", timeToMinute(event.target.value))} /></label> : <div className="presence-paired-fields"><label><span>从</span><input type="time" value={minuteToTime(draft.window_start_minute)} onChange={(event) => updateDraft("window_start_minute", timeToMinute(event.target.value))} /></label><label><span>到</span><input type="time" value={minuteToTime(draft.window_end_minute)} onChange={(event) => updateDraft("window_end_minute", timeToMinute(event.target.value))} /></label></div>}</fieldset>
          <fieldset><legend>联系间隔</legend><div className="presence-segmented"><button type="button" aria-pressed={draft.cadence_mode === "fixed"} className={`presence-interactive ${draft.cadence_mode === "fixed" ? "is-selected" : ""}`} onClick={() => updateDraft("cadence_mode", "fixed")}>固定间隔</button><button type="button" aria-pressed={draft.cadence_mode === "random_interval"} className={`presence-interactive ${draft.cadence_mode === "random_interval" ? "is-selected" : ""}`} onClick={() => updateDraft("cadence_mode", "random_interval")}>区间内随机</button></div>{draft.cadence_mode === "fixed" ? <label><span>每隔（小时）</span><input type="number" min="1" max="8760" value={draft.fixed_interval_minutes / 60} onChange={(event) => updateDraft("fixed_interval_minutes", Math.round(Number(event.target.value) * 60))} /></label> : <div className="presence-paired-fields"><label><span>最少（小时）</span><input type="number" min="1" max="8760" value={draft.random_interval_min_minutes / 60} onChange={(event) => updateDraft("random_interval_min_minutes", Math.round(Number(event.target.value) * 60))} /></label><label><span>最多（小时）</span><input type="number" min="1" max="8760" value={draft.random_interval_max_minutes / 60} onChange={(event) => updateDraft("random_interval_max_minutes", Math.round(Number(event.target.value) * 60))} /></label></div>}</fieldset>
        </div>
        <div className="presence-week-row"><span>可联系日期</span><div>{WEEKDAYS.map((label, index) => <button type="button" key={label} aria-pressed={draft.weekdays.includes(index)} className={`presence-interactive ${draft.weekdays.includes(index) ? "is-selected" : ""}`} onClick={() => updateDraft("weekdays", draft.weekdays.includes(index) ? draft.weekdays.filter((day) => day !== index) : [...draft.weekdays, index].sort())}>{label}</button>)}</div></div>
        <div className="presence-time-meta-grid"><label><span>统一时区</span><input value={draft.timezone} onChange={(event) => updateDraft("timezone", event.target.value)} /></label><label><span>每日联系上限</span><input type="number" min="0" max="100" value={draft.max_presence_per_day} onChange={(event) => updateDraft("max_presence_per_day", Number(event.target.value))} /><small>0 表示不增加每日上限，仍服从计划频率和安全预算。</small></label></div>
        <div className="presence-quiet-card">
          <div className="presence-switch-card"><span><strong><Moon size={16} /> 安静时段</strong><small>在这个时间窗内保持沉默；Hard stop、revoke 和 Focus mode 始终更高。</small></span><button type="button" role="switch" aria-checked={draft.quiet_hours.enabled} className={`presence-master-switch presence-interactive ${draft.quiet_hours.enabled ? "is-on" : ""}`} onClick={() => updateDraft("quiet_hours", { ...draft.quiet_hours, enabled: !draft.quiet_hours.enabled })}><span aria-hidden="true" />{draft.quiet_hours.enabled ? "已启用" : "已关闭"}</button></div>
          {draft.quiet_hours.enabled ? <div className="presence-paired-fields"><label><span>开始</span><input type="time" value={draft.quiet_hours.start} onChange={(event) => updateDraft("quiet_hours", { ...draft.quiet_hours, start: event.target.value })} /></label><label><span>结束</span><input type="time" value={draft.quiet_hours.end} onChange={(event) => updateDraft("quiet_hours", { ...draft.quiet_hours, end: event.target.value })} /></label></div> : null}
        </div>
      </section>

      <section className={`presence-runtime-strip ${dirty ? "has-draft" : ""}`} aria-label="主动联系运行状态">
        <div><Clock3 size={17} /><span>下一次</span><strong>{formatDate(configuration.runtime.next_occurrence_at)}</strong></div>
        <div><ShieldCheck size={17} /><span>最后发送</span><strong>{formatDate(configuration.runtime.last_delivered_at)}</strong></div>
        <div className="presence-save-actions"><button type="button" className="presence-secondary-action presence-interactive" disabled={!configuration.configuration.enabled || !configuration.versions.schedule_revision || dirty || triggering || saving} onClick={trigger}><RefreshCw size={15} className={triggering ? "is-spinning" : ""} />{triggering ? "正在检验并发送…" : dirty ? "请先保存" : "立即测试一次"}</button><button type="button" className="presence-primary-action presence-interactive" disabled={saving || !dirty} onClick={save}>{saving ? "正在完整保存…" : dirty ? "保存 Presence 设置" : "设置已保存"}</button></div>
      </section>

      <details className="presence-history" open><summary>最近运行记录 <span>{occurrences.length} 条</span></summary>{occurrences.length === 0 ? <p>还没有调度记录。启用并保存后，系统会固定下一次联系时间。</p> : <div>{occurrences.slice(0, 8).map((item) => <article key={item.id}><span className={`presence-run-state is-${item.status}`}>{item.status === "delivered" ? "已发送" : item.status === "scheduled" ? "已安排" : item.status === "suppressed" ? "保持沉默" : item.status === "retry_wait" ? "等待重试" : item.status}</span><strong>{formatDate(item.delivered_at || item.scheduled_for)}</strong><small>{readableReason(item.suppression_reason || item.error_code || (item.conversation_id ? "已写入 Web 对话" : null))}</small></article>)}</div>}</details>
      <details className="presence-history"><summary>待确认的 Presence 机会 <span>{queue.items.length} 条</span></summary>{queue.loading ? <p>正在读取……</p> : queue.error ? <p>暂时无法读取队列。</p> : queue.items.length === 0 ? <p>当前没有待处理机会；没有提醒也是一种有效决定。</p> : <div>{queue.items.slice(0, 8).map((item) => <article key={item.id}><span className="presence-run-state">{item.status}</span><strong>{item.title || item.type || "Presence"}</strong><small>{item.reason || item.message || "等待你的决定"}</small></article>)}</div>}</details>
    </div>
  );
}
