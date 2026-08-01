"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, Bot, CheckCircle2, CirclePause, ExternalLink, Link2,
  MessageCircle, Plus, RefreshCw, ShieldCheck, Unplug,
} from "lucide-react";
import * as companionApi from "@/lib/api/companions";
import * as conversationApi from "@/lib/api/conversations";
import {
  bindDiscordBotToCompanion,
  listDiscordBotIdentitiesStatus,
  listDiscordBotIdentityBindings,
  listDiscordDmBindings,
  listDiscordDmDeliveries,
  preflightDiscordBotRebind,
  testDiscordBotConnection,
  transitionDiscordDmBinding,
} from "@/lib/api/channelGateway";
import type { ConversationBrief } from "@/lib/api/conversations";
import type { DiscordBotIdentityStatus, DiscordDmBinding, DiscordDmDelivery } from "@/lib/types";
import {
  SettingsAction,
  SettingsInlineNotice,
  SettingsSectionHeading,
  SettingsStatusPill,
} from "@/components/settings/SettingsControls";
import { SettingsViewHeader } from "@/components/settings/SettingsView";


type CompanionOption = { id: string; name: string; current_mode: string };
type Notice = { tone: "success" | "error" | "info"; text: string } | null;


function formatTime(value?: string | null) {
  if (!value) return "尚无记录";
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}


function StatusPill({ status }: { status: string }) {
  const good = ["active", "delivered", "configured", "contract_verified", "bound"].includes(status);
  const warning = ["paused", "queued", "leased", "retry_scheduled", "missing", "unbound"].includes(status);
  return <SettingsStatusPill tone={good ? "success" : warning ? "warning" : "danger"}>{statusLabel(status)}</SettingsStatusPill>;
}


export function DiscordSettingsPage() {
  const [bots, setBots] = useState<DiscordBotIdentityStatus[]>([]);
  const [botBindings, setBotBindings] = useState<Record<string, string>>({});
  const [dmBindings, setDmBindings] = useState<DiscordDmBinding[]>([]);
  const [deliveries, setDeliveries] = useState<DiscordDmDelivery[]>([]);
  const [companions, setCompanions] = useState<CompanionOption[]>([]);
  const [conversations, setConversations] = useState<Record<string, ConversationBrief[]>>({});
  const [pendingCompanion, setPendingCompanion] = useState<Record<string, string>>({});
  const [pendingConversation, setPendingConversation] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<Notice>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    try {
      const [status, identities, dm, recent, companionResult] = await Promise.all([
        listDiscordBotIdentitiesStatus(),
        listDiscordBotIdentityBindings(),
        listDiscordDmBindings(),
        listDiscordDmDeliveries({ limit: 40 }),
        companionApi.listCompanions(),
      ]);
      const identityMap: Record<string, string> = {};
      for (const item of identities.bots || []) {
        if (item.binding?.companion_id) identityMap[item.bot_key] = item.binding.companion_id;
      }
      const companionPayload = companionResult as unknown as { items?: CompanionOption[]; data?: { items?: CompanionOption[] } };
      const companionItems = companionPayload.items || companionPayload.data?.items || [];
      const uniqueCompanionIds = [...new Set((dm.items || []).map(item => item.companion_id))];
      const conversationRows = await Promise.all(
        uniqueCompanionIds.map(async companionId => [
          companionId,
          (await conversationApi.listConversations({ companion_id: companionId, status: "active", page_size: 100 })).items || [],
        ] as const),
      );
      setBots(status.bots || []);
      setBotBindings(identityMap);
      setDmBindings(dm.items || []);
      setDeliveries(recent.items || []);
      setCompanions(companionItems);
      setConversations(Object.fromEntries(conversationRows));
    } catch (error) {
      setNotice({ tone: "error", text: error instanceof Error ? error.message : "Discord 状态读取失败。" });
    } finally {
      setLoading(false);
    }
  }, []);

  /* eslint-disable react-hooks/set-state-in-effect -- initial connected API hydration */
  useEffect(() => { void load(); }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const summary = useMemo(() => ({
    configured: bots.filter(bot => bot.token_status === "configured").length,
    companionBound: Object.keys(botBindings).length,
    activeDm: dmBindings.filter(item => item.binding_status === "active").length,
    pendingDelivery: deliveries.filter(item => ["queued", "leased", "retry_scheduled"].includes(item.delivery_status)).length,
  }), [bots, botBindings, dmBindings, deliveries]);
  const pendingDmBots = useMemo(() => {
    const botsWithDmState = new Set(
      dmBindings.flatMap((binding) => binding.bot_key ? [binding.bot_key] : []),
    );
    return bots.filter((bot) => !botsWithDmState.has(bot.bot_key));
  }, [bots, dmBindings]);
  const companionNameById = useMemo(
    () => new Map(companions.map((companion) => [companion.id, companion.name])),
    [companions],
  );

  const runAction = async (key: string, action: () => Promise<unknown>, success: string) => {
    setBusy(key);
    setNotice(null);
    try {
      await action();
      await load();
      setNotice({ tone: "success", text: success });
    } catch (error) {
      setNotice({ tone: "error", text: error instanceof Error ? error.message : "操作未完成。" });
    } finally {
      setBusy(null);
    }
  };

  const rebindBot = async (botKey: string, companionId: string) => {
    await runAction(`bind:${botKey}`, async () => {
      const preflight = await preflightDiscordBotRebind({ bot_key: botKey, companion_id: companionId });
      let dependencyAction: "reject" | "pause" = "reject";
      if (preflight.requires_explicit_pause) {
        const dependencies = preflight.dependencies || {};
        const confirmed = window.confirm(
          `改绑会暂停 ${dependencies.live_dm_binding_count || 0} 个 DM 绑定、${dependencies.live_room_binding_count || 0} 个频道/聊天室绑定，并取消 ${dependencies.pending_delivery_count || 0} 条待投递回复。旧 Conversation 不会迁移。继续吗？`,
        );
        if (!confirmed) throw new Error("已取消 Bot–Companion 改绑。");
        dependencyAction = "pause";
      }
      return bindDiscordBotToCompanion({
        bot_key: botKey,
        companion_id: companionId,
        expected_revision: preflight.current_identity?.revision,
        dependency_action: dependencyAction,
      });
    }, "Bot–Companion 一一绑定已更新；受影响依赖已按确认暂停，旧 Conversation 未迁移。");
  };

  return (
    <main className="settings-native-view settings-discord-workspace">
      <SettingsViewHeader
        eyebrow="设置 / 渠道"
        title="Discord 私信连续性"
        description="每个 Bot 只属于一位伙伴。首次私信会锁定 Discord 身份并建立持久 Web Conversation，之后的入站与回复继续写入 Web。"
        icon={MessageCircle}
        aside={<><strong>Web 是持久真值</strong><p>Bot 改绑不会迁移旧 Conversation；配置核验也不冒充 Gateway 在线证明。</p></>}
      />
      <div className="settings-toolbar"><SettingsAction busy={loading} disabled={busy !== null} onClick={() => void load()}><RefreshCw size={15} aria-hidden />刷新状态</SettingsAction></div>
      {notice ? <SettingsInlineNotice tone={notice.tone === "error" ? "danger" : notice.tone}>{notice.text}</SettingsInlineNotice> : null}

      <section className="settings-metric-strip" aria-label="Discord 连续性概览">
        <Metric label="令牌已配置" value={`${summary.configured}/${bots.length}`} />
        <Metric label="Bot–Companion" value={`${summary.companionBound}/${bots.length}`} />
        <Metric label="活跃私信绑定" value={String(summary.activeDm)} />
        <Metric label="待投递 / 重试" value={String(summary.pendingDelivery)} />
      </section>

      <section className="settings-domain-section">
        <SettingsSectionHeading icon={Bot} title="Bot 与伙伴" description="测试按钮只核验配置合同，不冒充真实 Gateway 在线证明。" />
        {loading ? <LoadingState /> : bots.length === 0 ? <EmptyState text="未检测到本地 Discord Bot Registry。" /> : (
          <div className="grid gap-4 lg:grid-cols-2">
            {bots.map(bot => {
              const boundCompanion = botBindings[bot.bot_key];
              const selected = pendingCompanion[bot.bot_key] ?? boundCompanion ?? "";
              return (
                <article key={bot.bot_key} className="settings-entity-row">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-medium" style={{ color: "var(--echora-text-primary)" }}>{bot.bot_display_name || bot.bot_key}</h3>
                      <p className="mt-1 text-xs" style={{ color: "var(--echora-text-muted)" }}>{bot.bot_key}</p>
                    </div>
                    <StatusPill status={boundCompanion ? "bound" : "unbound"} />
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                    <Fact label="Token" value={bot.token_status} />
                    <Fact label="Application ID" value={bot.app_id || bot.application_id ? "configured" : "missing"} />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <select
                      className="min-h-11 min-w-52 rounded-xl border px-3 text-sm focus:outline-none focus:ring-2"
                      style={{ background: "rgba(255,255,255,.72)", borderColor: "rgba(130,164,195,.24)", color: "var(--echora-text-primary)" }}
                      aria-label={`${bot.bot_display_name || bot.bot_key} 绑定 Companion`}
                      value={selected}
                      onChange={event => setPendingCompanion(current => ({ ...current, [bot.bot_key]: event.target.value }))}
                    >
                      <option value="">选择 Companion</option>
                      {companions.map(companion => <option key={companion.id} value={companion.id}>{companion.name}</option>)}
                    </select>
                    <button
                      className="act-btn act-btn-primary min-h-11"
                      disabled={!selected || selected === boundCompanion || busy !== null}
                      onClick={() => void rebindBot(bot.bot_key, selected)}
                    ><Link2 size={14} aria-hidden /> 保存绑定</button>
                    <button
                      className="act-btn min-h-11"
                      disabled={busy !== null}
                      onClick={() => void runAction(
                        `test:${bot.bot_key}`,
                        () => testDiscordBotConnection({ bot_key: bot.bot_key }),
                        "配置合同核验完成；真实在线状态仍以 Gateway runtime 为准。",
                      )}
                    ><Activity size={14} aria-hidden /> 核验配置</button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="settings-domain-section">
        <SettingsSectionHeading icon={ShieldCheck} title="持久 DM 绑定" description="每个已配置 Bot 都会显示。首次私信前只展示准备状态，不伪造 Discord identity 或 Conversation。" />
        {pendingDmBots.length === 0 && dmBindings.length === 0 ? <EmptyState text="尚未配置 Discord Bot。请先在模型与连接中添加 Bot，并在上方绑定伙伴。" /> : (
          <div className="space-y-4">
            {pendingDmBots.map((bot) => {
              const companionId = botBindings[bot.bot_key];
              const companionName = companionId ? companionNameById.get(companionId) : null;
              return (
                <article key={`pending:${bot.bot_key}`} className="settings-entity-row">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="font-medium" style={{ color: "var(--echora-text-primary)" }}>
                        {companionName || "尚未绑定伙伴"} · {bot.bot_display_name || bot.bot_key}
                      </h3>
                      <p className="mt-1 text-xs" style={{ color: "var(--echora-text-muted)" }}>
                        {companionId
                          ? "Bot 与伙伴已准备好；Discord 用户尚未发送首次私信。"
                          : "请先在上方选择这位 Bot 所属的伙伴。"}
                      </p>
                    </div>
                    <SettingsStatusPill tone="warning">{companionId ? "等待首次私信" : "等待伙伴绑定"}</SettingsStatusPill>
                  </div>
                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    <Fact label="Bot" value={bot.bot_display_name || bot.bot_key} />
                    <Fact label="伙伴" value={companionName || "尚未选择"} />
                    <Fact label="Conversation" value="首次私信后建立" />
                  </div>
                  <p className="mt-3 text-xs leading-6" style={{ color: "var(--echora-text-muted)" }}>
                    首次 DM 会锁定 Discord identity，并为这位伙伴建立持久 Web Conversation；此处不会预先创建空对话。
                  </p>
                </article>
              );
            })}
            {dmBindings.map(binding => {
              const options = conversations[binding.companion_id] || [];
              const selected = pendingConversation[binding.id] ?? binding.conversation_id;
              const revoked = binding.binding_status === "revoked";
              return (
                <article key={binding.id} className="settings-entity-row">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="font-medium" style={{ color: "var(--echora-text-primary)" }}>{binding.companion_name || "Companion"} · {binding.bot_display_name || binding.bot_key}</h3>
                      <p className="mt-1 text-xs" style={{ color: "var(--echora-text-muted)" }}>Discord identity 已建立，并持续写入同一段 Web 对话。</p>
                    </div>
                    <StatusPill status={binding.binding_status} />
                  </div>
                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    <Fact label="当前 Conversation" value={binding.conversation_title || "Discord 私信对话"} />
                    <Fact label="最后入站" value={formatTime(binding.last_inbound_at)} />
                    <Fact label="最后投递" value={formatTime(binding.last_outbound_at)} />
                  </div>
                  <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end">
                    <label className="min-w-0 flex-1 text-xs font-medium" style={{ color: "var(--echora-text-muted)" }}>
                      <span className="mb-2 block">所绑定的对话</span>
                      <select
                        className="min-h-11 w-full rounded-xl border px-3 text-sm focus:outline-none focus:ring-2"
                        style={{ background: "rgba(255,255,255,.72)", borderColor: "rgba(130,164,195,.24)", color: "var(--echora-text-primary)" }}
                        value={selected}
                        disabled={revoked || busy !== null}
                        aria-label="选择 Discord 对应的 Web Conversation"
                        onChange={event => {
                          const conversationId = event.target.value;
                          setPendingConversation(current => ({ ...current, [binding.id]: conversationId }));
                          if (conversationId === binding.conversation_id) return;
                          void runAction(
                            `switch:${binding.id}`,
                            () => transitionDiscordDmBinding(binding.id, "switch", { expected_revision: binding.revision, conversation_id: conversationId }),
                            "Discord 私信已切换到所选 Web Conversation。",
                          );
                        }}
                      >
                        {options.map(conversation => <option key={conversation.id} value={conversation.id}>{conversation.title || "未命名对话"}</option>)}
                      </select>
                    </label>
                    <button
                      className="act-btn min-h-11"
                      disabled={revoked || busy !== null}
                      onClick={() => void runAction(
                        `new:${binding.id}`,
                        () => transitionDiscordDmBinding(binding.id, "new", { expected_revision: binding.revision }),
                        "已新建并切换 Discord 私信 Conversation。",
                      )}
                    ><Plus size={14} aria-hidden /> 新建并选择</button>
                  </div>
                  <p className="mt-2 flex items-center gap-1 text-xs" style={{ color: "var(--echora-text-muted)" }}>
                    <CheckCircle2 size={14} aria-hidden /> 当前选择：{binding.conversation_title || "Discord 私信对话"}
                  </p>
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    {binding.binding_status === "active" ? (
                      <button className="act-btn min-h-11" disabled={busy !== null} onClick={() => void runAction(
                        `pause:${binding.id}`,
                        () => transitionDiscordDmBinding(binding.id, "pause", { expected_revision: binding.revision }),
                        "Discord 私信回复已暂停。",
                      )}><CirclePause size={14} aria-hidden /> 暂停</button>
                    ) : binding.binding_status === "paused" ? (
                      <button className="act-btn min-h-11" disabled={busy !== null} onClick={() => void runAction(
                        `resume:${binding.id}`,
                        () => transitionDiscordDmBinding(binding.id, "resume", { expected_revision: binding.revision }),
                        "Discord 私信回复已恢复。",
                      )}><CheckCircle2 size={14} aria-hidden /> 恢复</button>
                    ) : null}
                    {!revoked && (
                      <button
                        className="act-btn min-h-11"
                        disabled={busy !== null}
                        onClick={() => {
                          if (!window.confirm("撤销后不可恢复，且待发送回复会被取消。确定继续吗？")) return;
                          void runAction(
                            `revoke:${binding.id}`,
                            () => transitionDiscordDmBinding(binding.id, "revoke", { expected_revision: binding.revision }),
                            "Discord 私信绑定已撤销。",
                          );
                        }}
                      ><Unplug size={14} aria-hidden /> 撤销</button>
                    )}
                    <Link className="act-btn min-h-11" href={`/companions/${binding.companion_id}/conversations/${binding.conversation_id}`}>
                      <ExternalLink size={14} aria-hidden /> 打开会话
                    </Link>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="settings-domain-section">
        <SettingsSectionHeading icon={Activity} title="最近投递证据" description="成功终态单调保留；失败只记录结构化摘要，不展示 Discord 原始标识或 Provider 响应正文。" />
        {deliveries.length === 0 ? <div className="mt-4"><EmptyState text="尚无 Discord DM 投递记录。" /></div> : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead><tr style={{ color: "var(--echora-text-muted)" }}><th className="pb-3 font-medium">状态</th><th className="pb-3 font-medium">尝试</th><th className="pb-3 font-medium">Conversation</th><th className="pb-3 font-medium">时间</th><th className="pb-3 font-medium">失败摘要</th></tr></thead>
              <tbody>
                {deliveries.map(item => (
                  <tr key={item.id} className="border-t" style={{ borderColor: "rgba(130,164,195,.15)", color: "var(--echora-text-secondary)" }}>
                    <td className="py-3"><StatusPill status={item.delivery_status} /></td>
                    <td className="py-3">{item.attempt_count}/{item.max_attempts}</td>
                    <td className="py-3 font-mono text-xs">{item.conversation_id.slice(0, 8)}</td>
                    <td className="py-3">{formatTime(item.delivered_at || item.updated_at)}</td>
                    <td className="py-3">{item.last_error_summary || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}


function Metric({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}


function Fact({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl px-3 py-2" style={{ background: "rgba(255,255,255,.42)" }}><div className="text-[11px]" style={{ color: "var(--echora-text-muted)" }}>{label}</div><div className="mt-1 truncate text-xs" style={{ color: "var(--echora-text-secondary)" }}>{value}</div></div>;
}


function EmptyState({ text }: { text: string }) {
  return <div className="settings-empty-state">{text}</div>;
}


function LoadingState() {
  return <SettingsInlineNotice><RefreshCw size={15} className="animate-spin" aria-hidden /> 正在读取 Discord 连续性…</SettingsInlineNotice>;
}

function statusLabel(status: string) {
  return ({
    active: "已启用", delivered: "已投递", configured: "已配置", contract_verified: "已核验",
    bound: "已绑定", paused: "已暂停", queued: "排队中", leased: "处理中",
    retry_scheduled: "等待重试", missing: "缺少配置", unbound: "未绑定", revoked: "已撤销",
    failed: "失败", cancelled: "已取消",
  } as Record<string, string>)[status] ?? status;
}
