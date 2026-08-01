"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { LockKeyhole, Radio, ShieldCheck, UserRound } from "lucide-react";
import { companionProfilesApi } from "@/lib/api/companionProfiles";
import { useCompanionWorkspaceQuery } from "@/lib/queries/companions";
import { DataState } from "@/components/patterns/DataState";
import { SettingsViewHeader } from "@/components/settings/SettingsView";
import { CompanionOwnerProfile } from "@/features/profile/CompanionOwnerProfile";

export function CompanionProfile({ companionId }: { companionId: string }) {
  const workspace = useCompanionWorkspaceQuery(companionId);
  const profiles = useQueries({ queries: ["identity", "persona", "contract", "boundary", "visibility"].map((kind) => ({ queryKey: ["companions", companionId, kind], queryFn: () => companionProfilesApi[kind as "identity" | "persona" | "contract" | "boundary" | "visibility"](companionId) })) });
  if (workspace.isLoading || profiles.some((item) => item.isLoading)) return <DataState kind="loading" title="正在读取伙伴档案" />;
  if (workspace.isError || profiles.some((item) => item.isError) || !workspace.data) return <DataState kind="error" title="暂时无法读取伙伴档案" />;
  const [identity, persona, contract, boundary, visibility] = profiles.map((item) => item.data ?? {});
  const governance = workspace.data.governance;
  const channels = workspace.data.channels;
  const presence = workspace.data.channel_presence;
  const voice = workspace.data.voice;
  const governanceMeta = governance ? `Hard stop：${governance.hard_stop_active ? governance.hard_stop_scope : "未启用"} · 已撤销频道：${governance.revoked_channels}` : "治理摘要：尚未提供";
  const governanceContent = governance ? (governance.hard_stop_active ? "当前伙伴或全局实时范围已启用 hard stop；主动在场与发送路径应被阻断。" : "当前没有作用于这位伙伴的 active hard stop。频道撤销状态按真实绑定记录显示。") : "当前运行后端尚未返回治理摘要；不会将缺失数据误显示为未启用。";
  const channelMeta = channels ? `绑定：${channels.length} · 活跃：${channels.filter((item) => item.status === "active").length}` : "渠道摘要：尚未提供";
  const channelContent = channels ? (channels.length ? `频道记忆始终保持审核：${channels.every((item) => item.memory_review_required) ? "是" : "存在非默认策略"}。${presence?.some((item) => item.muted) ? "部分频道已静音。" : "当前没有频道静音。"}` : "当前没有渠道绑定。") : "当前运行后端尚未返回渠道与 Presence 策略摘要。";
  const voiceMeta = voice?.profile_status ? `档案：${voice.profile_status} · 会话：${voice.session_status || "无"}` : voice ? "语音档案：未配置" : "语音摘要：尚未提供";
  const voiceContent = voice ? (voice.profile_status ? `语音档案“${voice.profile_name || "未命名"}”已配置；转写保留策略为 ${voice.transcript_retention || "未启用"}，记忆写入策略为 ${voice.memory_write_policy || "candidate_review"}。${voice.real_audio_enabled ? "已报告真实音频能力。" : "未声明真实音频能力。"}` : "尚未为这位伙伴配置语音档案；不会将其表述为可用语音。") : "当前运行后端尚未返回语音准备度摘要。";
  const displayName = String(identity.display_name || workspace.data.companion.name);
  const identitySummary = String(identity.identity_summary || workspace.data.identity.identity_summary);
  return <main className="settings-native-view companion-profile-page settings-profile-workspace">
    <SettingsViewHeader
      eyebrow="设置 / 伙伴档案"
      title={displayName}
      description={identitySummary}
      icon={UserRound}
      aside={<><strong>稳定身份与独立边界</strong><p>这里只管理这位伙伴的身份、关系约定与读取范围；Presence 节奏继续由其唯一页面负责。</p></>}
    />
    <section className="profile-intro-strip" aria-label="伙伴档案范围">
      <span>身份与关系可编辑</span>
      <span>Presence 仅展示摘要</span>
      <span>跨伙伴读取默认阻止</span>
    </section>
    <section className="profile-primary-actions" aria-label="伙伴档案主要操作">
      <CompanionOwnerProfile companionId={companionId} identity={identity} persona={persona} contract={contract} boundary={boundary} />
    </section>
    <section className="profile-secondary-actions" aria-label="伙伴管理与安全">
      <header><small>管理与安全</small><h2>需要时再调整的次级功能</h2><p>陪伴节奏、记忆可见范围、数据快照和关系生命周期不会打断个人档案的主要体验。</p></header>
      <div>
      <PresenceOwnerSummary companionId={companionId} persona={persona} boundary={boundary} />
      <VisibilitySection companionId={companionId} visibility={visibility} />
      <RelationshipDataSection companionId={companionId} profiles={{ identity, persona, contract, boundary, visibility }} />
      <LifecycleSection companionId={companionId} identity={identity} />
      </div>
    </section>
    <details className="profile-advanced-details">
      <summary><span>查看系统如何保护这份档案</span><small>人格锁定、跨伙伴边界、渠道与能力准备度</small></summary>
      <div className="profile-grid">
        <ProfileSection title="人格稳定性" content={String(persona.persona_summary || workspace.data.identity.persona_summary)} meta={`保护级别：${personaLockLabel(String(persona.persona_lock_level || "guarded"))}`} />
        <ProfileSection title="共享与跨伙伴边界" content="私有记忆、共享记忆和跨伙伴读取都遵循明确的审核与可见性策略。" meta={`跨伙伴读取：${boundaryLabel(String(boundary.cross_companion_read_policy || "blocked"))}`} icon={<ShieldCheck size={19} />} />
        <ProfileSection title="当前安全边界" content={governanceContent} meta={governanceMeta} icon={<ShieldCheck size={19} />} />
        <ProfileSection title="渠道连续性" content={channelContent} meta={channelMeta} />
        <ProfileSection title="未来语音能力" content={voiceContent} meta={voiceMeta} />
      </div>
    </details>
  </main>;
}

function PresenceOwnerSummary({ companionId, persona, boundary }: { companionId: string; persona: Record<string, unknown>; boundary: Record<string, unknown> }) {
  const quiet = record(record(boundary.boundary_json).quiet_hours);
  const style = ({ quiet: "克制", balanced: "自然", expressive: "积极" } as Record<string, string>)[String(persona.presence_style || "balanced")] || "自然";
  const interrupt = boundary.presence_interrupt_policy === "user_initiated_only" ? "仅由你发起" : "遵守当前边界";
  return <article className="profile-section profile-presence-summary"><Radio size={19} /><small>Presence 摘要 · 只读</small><h2>{style}陪伴 · {interrupt}</h2><p>{quiet.enabled === false ? "未设置固定安静时段。" : `安静时段 ${String(quiet.start || "23:00")}–${String(quiet.end || "08:00")}。`} 具体节奏、通知与 meaningful silence 只在 Presence 修改。</p><Link className="profile-action" href={`/settings/companions/${companionId}/presence`}>管理 Presence</Link></article>;
}

function record(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }

function LifecycleSection({ companionId, identity }: { companionId: string; identity: Record<string, unknown> }) {
  const archived = identity.profile_status === "archived";
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const client = useQueryClient();
  const transition = useMutation({ mutationFn: () => (archived ? companionProfilesApi.restore : companionProfilesApi.archive)(companionId, { expected_identity_updated_at: identity.updated_at, confirm_preserve_history: confirmed, confirm_boundaries_and_channels: archived && confirmed }), onSuccess: async () => {
    await Promise.all([client.invalidateQueries({ queryKey: ["companions"] }), client.invalidateQueries({ queryKey: ["companions", companionId, "identity"] }), client.invalidateQueries({ queryKey: ["companions", companionId, "chronicle"] })]);
    if (!archived) window.location.assign("/"); else { setConfirming(false); setConfirmed(false); }
  } });
  return <article className="profile-section profile-lifecycle"><small>关系生命周期</small><h2>{archived ? "当前已归档" : "当前共同生活中"}</h2><p>{archived ? "历史对话、记忆、共同历程与审计都还在；恢复前需要重新确认边界与渠道状态。" : "归档不会删除关系历史；它会退出默认星图，并阻断新的主动 Presence 与渠道外发。"}</p>{confirming ? <div className="lifecycle-confirm"><label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />{archived ? "我已重新确认边界与渠道状态，理解旧 Presence 队列不会自动恢复。" : "我理解归档会停止主动在场与外发，但不会删除任何关系数据。"}</label><div><button type="button" disabled={!confirmed || transition.isPending} onClick={() => transition.mutate()}>{transition.isPending ? "正在处理…" : archived ? "确认恢复" : "确认归档"}</button><button type="button" disabled={transition.isPending} onClick={() => { setConfirming(false); setConfirmed(false); transition.reset(); }}>取消</button></div>{transition.isError ? <span role="alert">操作失败；若状态已变化，请刷新后重新确认。</span> : null}</div> : <button type="button" className="profile-action" onClick={() => setConfirming(true)}>{archived ? "恢复这段关系" : "归档这段关系"}</button>}</article>;
}

function RelationshipDataSection({ companionId, profiles }: { companionId: string; profiles: Record<string, Record<string, unknown>> }) {
  const download = () => {
    const blob = new Blob([JSON.stringify({ schema: "echora.relationship-profile.v1", exported_at: new Date().toISOString(), companion_id: companionId, ...profiles }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `echora-relationship-${companionId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };
  return <article className="profile-section"><small>关系数据</small><h2>下载当前关系档案</h2><p>导出当前身份、表达、关系约定、边界与可见性快照。它不是完整消息、媒体或生产级数据权利包。</p><button type="button" className="profile-action" onClick={download}>下载 JSON 快照</button></article>;
}

function VisibilitySection({ companionId, visibility }: { companionId: string; visibility: Record<string, unknown> }) {
  const [editing, setEditing] = useState(false); const [confirmed, setConfirmed] = useState(false); const [allowSensitive, setAllowSensitive] = useState(Boolean(visibility.allow_sensitive_global_read)); const [allowPrivate, setAllowPrivate] = useState(Boolean(visibility.allow_other_companion_private_read)); const client = useQueryClient();
  const save = useMutation({ mutationFn: () => companionProfilesApi.patchVisibility(companionId, { allow_sensitive_global_read: allowSensitive, allow_other_companion_private_read: allowPrivate }), onSuccess: () => { client.invalidateQueries({ queryKey: ["companions", companionId, "visibility"] }); client.invalidateQueries({ queryKey: ["companions", companionId, "chronicle"] }); setEditing(false); setConfirmed(false); } });
  return <article className="profile-section"><LockKeyhole size={19} /><small>可见性策略</small><h2>全局范围：{String(visibility.user_global_memory_scope || "low_risk_summary_only")}</h2><p>敏感全局记忆与其他伙伴的私有记忆默认不可读取；变更将写入审计轨迹。这只管理读取范围，不改变记忆保存策略或 Conversation 保留方式。</p><Link className="profile-action" href={`/settings/companions/${companionId}/memory`}>前往记忆保存策略</Link>{editing ? <div className="visibility-editor"><label><input type="checkbox" checked={allowSensitive} onChange={(event) => setAllowSensitive(event.target.checked)} />允许读取敏感全局记忆</label><label><input type="checkbox" checked={allowPrivate} onChange={(event) => setAllowPrivate(event.target.checked)} />允许读取其他伙伴的私有记忆</label><label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />我已理解：这会扩大当前伙伴的可见范围，并保留可追溯审计记录。</label><button type="button" disabled={!confirmed || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "正在保存" : "确认并保存"}</button><button type="button" onClick={() => setEditing(false)}>取消</button>{save.isError ? <p>保存失败，请检查连接后重试。</p> : null}</div> : <button type="button" className="profile-action" onClick={() => setEditing(true)}>修改可见性策略</button>}</article>;
}

function ProfileSection({ title, content, meta, icon }: { title: string; content: string; meta: string; icon?: React.ReactNode }) { return <article className="profile-section">{icon}<small>{title}</small><h2>{meta}</h2><p>{content}</p></article>; }
function personaLockLabel(value: string) { return ({ guarded: "保护核心人格", locked: "锁定核心人格", flexible: "允许有限成长" } as Record<string, string>)[value] ?? "保护核心人格"; }
function boundaryLabel(value: string) { return ({ blocked: "默认阻止", review_required: "需要确认", allowed: "已明确允许" } as Record<string, string>)[value] ?? "按边界处理"; }
