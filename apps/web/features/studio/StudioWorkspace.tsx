"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Bot, FlaskConical, FolderKanban, GitCompareArrows, KeyRound, Network, RadioTower, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import { DataState } from "@/components/patterns/DataState";
import { ConfirmActionDialog } from "@/components/patterns/ConfirmActionDialog";
import { activateChannelBinding, disableChannelBinding, listDiscordBotIdentitiesStatus, revokeChannelBinding } from "@/lib/api/channelGateway";
import { createReplayBadCase, createReplayFromTrace, createReplayRegressionCase } from "@/lib/api/replays";
import { getActivationGate, getStudioDatabaseHealth, getStudioEnvironment, getStudioHealth, listStudio, type StudioList } from "@/lib/api/studio";

type Area = "quality" | "integrations" | "system";
type Item = Record<string, unknown>;

const titles: Record<Area, { eyebrow: string; title: string; description: string }> = {
  quality: { eyebrow: "Studio / 质量", title: "质量与证据", description: "从真实 Trace、评测、回归、Bad Case 与 Replay 读取运行证据。" },
  integrations: { eyebrow: "Studio / 集成", title: "项目与集成", description: "查看项目、工具、渠道和 Discord 的受控连接状态。" },
  system: { eyebrow: "Studio / 系统", title: "系统状态与策略", description: "只读查看 Provider、权限、诊断和 Shadow 策略证据。" },
};

function value(item: Item, key: string) {
  const itemValue = item[key];
  return typeof itemValue === "string" || typeof itemValue === "number" || typeof itemValue === "boolean" ? String(itemValue) : "—";
}

function itemTitle(item: Item) {
  for (const key of ["title", "name", "bot_display_name", "audit_summary", "revoke_reason", "agent_graph_name", "provider_name", "model_name", "binding_scope", "summary", "prompt_key"]) {
    const candidate = value(item, key);
    if (candidate !== "—") return candidate;
  }
  const id = value(item, "id");
  return id === "—" ? "运行记录" : `运行记录 · ${id.slice(0, 8)}`;
}

function ListPanel({ title, icon: Icon, data, empty }: { title: string; icon: typeof Activity; data?: StudioList<Item>; empty: string }) {
  const items = data?.items ?? [];
  return (
    <section className="studio-panel">
      <div className="studio-panel-heading"><span><Icon size={16} aria-hidden="true" />{title}<small>最近 {items.length} 条 · 共 {data?.pagination.total ?? items.length} 条</small></span></div>
      {items.length ? <div className="studio-list">{items.map((item, index) => <div className="studio-row" key={String(item.id ?? index)}><div><strong>{itemTitle(item)}</strong><small>{value(item, "created_at") !== "—" ? value(item, "created_at") : "来自当前真实记录"}</small></div><span>{value(item, "status")}</span></div>)}</div> : <p className="studio-empty">{empty}</p>}
    </section>
  );
}

function useStudioList(key: string, path: string) {
  return useQuery({ queryKey: ["studio", key], queryFn: () => listStudio<Item>(path), staleTime: 15_000 });
}

function StudioQuality() {
  const [pendingTraceId, setPendingTraceId] = useState<string | null>(null);
  const [pendingReplayAction, setPendingReplayAction] = useState<{ id: string; kind: "bad-case" | "regression" } | null>(null);
  const [creatingReplay, setCreatingReplay] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const traces = useStudioList("traces", "/traces");
  const evaluations = useStudioList("evaluation-runs", "/evaluation-runs");
  const regressions = useStudioList("regression-runs", "/regression-runs");
  const badCases = useStudioList("bad-case-inbox", "/bad-case-inbox");
  const replays = useStudioList("replays", "/replays");
  const gate = useQuery({ queryKey: ["studio", "activation-gate"], queryFn: getActivationGate, staleTime: 15_000 });
  const qualityQueries = [traces, evaluations, regressions, badCases, replays, gate];
  const failed = qualityQueries.every((query) => query.isError);
  const partial = qualityQueries.some((query) => query.isLoading || query.isError);
  if (failed) return <DataState kind="error" title="质量数据暂不可用" description="请确认 Agent API 基线与当前 base URL。" />;
  async function confirmReplay() {
    if (!pendingTraceId) return;
    setCreatingReplay(true);
    setActionError(null);
    try {
      await createReplayFromTrace(pendingTraceId);
      await Promise.all([traces.refetch(), replays.refetch()]);
      setPendingTraceId(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "无法创建 Replay。");
    } finally {
      setCreatingReplay(false);
    }
  }
  async function confirmReplayFollowup() {
    if (!pendingReplayAction) return;
    setCreatingReplay(true);
    setActionError(null);
    try {
      const { id, kind } = pendingReplayAction;
      await (kind === "bad-case" ? createReplayBadCase(id) : createReplayRegressionCase(id));
      await Promise.all([replays.refetch(), badCases.refetch(), regressions.refetch()]);
      setPendingReplayAction(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "无法创建质量记录。");
    } finally {
      setCreatingReplay(false);
    }
  }
  return <>
    <section className="studio-policy-banner"><ShieldCheck size={18} aria-hidden="true" /><div><strong>Activation gate 仍关闭</strong><p>学习策略仅收集 Shadow 证据，不改变当前启发式决策。</p></div><span>{value(gate.data ?? {}, "status")}</span></section>
    {partial ? <p className="studio-partial-note">部分质量证据仍在读取或暂不可用；已返回的数据会先展示。</p> : null}
    {actionError ? <p className="studio-action-error" role="alert">{actionError}</p> : null}
    <div className="studio-grid"><section className="studio-panel"><div className="studio-panel-heading"><span><Network size={16} aria-hidden="true" />Trace</span></div>{traces.data?.items.length ? <div className="studio-list">{traces.data.items.map((trace, index) => <div className="studio-row" key={String(trace.id ?? index)}><div><strong>{itemTitle(trace)}</strong><small>{value(trace, "created_at")}</small></div><div className="studio-row-actions"><span>{value(trace, "status")}</span><button type="button" onClick={() => setPendingTraceId(value(trace, "id"))}>创建 Replay</button></div></div>)}</div> : <p className="studio-empty">暂无可读取的 Trace。</p>}</section><ListPanel title="评测运行" icon={FlaskConical} data={evaluations.data} empty="暂无评测运行。" /><ListPanel title="回归运行" icon={GitCompareArrows} data={regressions.data} empty="暂无回归运行。" /><ListPanel title="Bad Case" icon={Sparkles} data={badCases.data} empty="暂无待分诊 Bad Case。" /><section className="studio-panel"><div className="studio-panel-heading"><span><Activity size={16} aria-hidden="true" />Replay</span></div>{replays.data?.items.length ? <div className="studio-list">{replays.data.items.map((replay, index) => <div className="studio-row" key={String(replay.id ?? index)}><div><strong>{itemTitle(replay)}</strong><small>{value(replay, "created_at")}</small></div><div className="studio-row-actions"><button type="button" onClick={() => setPendingReplayAction({ id: value(replay, "id"), kind: "bad-case" })}>标记 Bad Case</button><button type="button" onClick={() => setPendingReplayAction({ id: value(replay, "id"), kind: "regression" })}>转回归</button></div></div>)}</div> : <p className="studio-empty">暂无可回放记录。</p>}</section></div>
    {pendingTraceId ? <ConfirmActionDialog title="从 Trace 创建 Replay" description="将保存当前 Trace 的输入、步骤与输出快照，用于后续回放和质量审查。" confirmLabel="创建 Replay" cancelLabel="暂不创建" busy={creatingReplay} onConfirm={confirmReplay} onCancel={() => setPendingTraceId(null)} /> : null}
    {pendingReplayAction ? <ConfirmActionDialog title={pendingReplayAction.kind === "bad-case" ? "标记为 Bad Case" : "创建回归用例"} description={pendingReplayAction.kind === "bad-case" ? "将从该 Replay 创建一条待分诊 Bad Case，并保留 Trace 关联。" : "将从该 Replay 创建一条回归用例，供后续质量验证。"} confirmLabel="确认创建" cancelLabel="暂不创建" busy={creatingReplay} onConfirm={confirmReplayFollowup} onCancel={() => setPendingReplayAction(null)} /> : null}
  </>;
}

function StudioIntegrations() {
  const [pendingBindingAction, setPendingBindingAction] = useState<{ id: string; action: "activate" | "disable" | "revoke" } | null>(null);
  const [savingBinding, setSavingBinding] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const tasks = useStudioList("project-tasks", "/project-tasks");
  const tools = useStudioList("tool-definitions", "/tool-definitions");
  const bindings = useStudioList("channel-bindings", "/channel-bindings");
  const audits = useStudioList("channel-audit-logs", "/channel-audit-logs");
  const revokes = useStudioList("channel-revoke-events", "/channel-revoke-events");
  const discord = useQuery({ queryKey: ["studio", "discord-status"], queryFn: listDiscordBotIdentitiesStatus, staleTime: 15_000 });
  const integrationQueries = [tasks, tools, bindings, audits, revokes, discord];
  const failed = integrationQueries.every((query) => query.isError);
  const partial = integrationQueries.some((query) => query.isLoading || query.isError);
  if (failed) return <DataState kind="error" title="集成数据暂不可用" description="请确认 Agent API 基线与当前 base URL。" />;
  const discordBots: StudioList<Item> | undefined = discord.data
    ? { items: (discord.data.bots ?? []).slice(0, 5) as unknown as Item[], pagination: { page: 1, page_size: 5, total: discord.data.bots?.length ?? 0, total_pages: Math.max(1, Math.ceil((discord.data.bots?.length ?? 0) / 5)) } }
    : undefined;
  async function confirmBindingAction() {
    if (!pendingBindingAction) return;
    setSavingBinding(true);
    setActionError(null);
    try {
      const { id, action } = pendingBindingAction;
      const payload = { reason: `studio_${action}` };
      if (action === "activate") await activateChannelBinding(id, payload);
      if (action === "disable") await disableChannelBinding(id, payload);
      if (action === "revoke") await revokeChannelBinding(id, payload);
      await Promise.all([bindings.refetch(), audits.refetch(), revokes.refetch()]);
      setPendingBindingAction(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "无法更新渠道绑定。");
    } finally {
      setSavingBinding(false);
    }
  }
  return <>
    <section className="studio-policy-banner"><ShieldCheck size={18} aria-hidden="true" /><div><strong>渠道操作继续受边界约束</strong><p>绑定、外发、memory review 与 revoke 均需通过既有审核和审计路径。</p></div><span>{value(discord.data ?? {}, "registry_status")}</span></section>
    {partial ? <p className="studio-partial-note">部分集成数据仍在读取或暂不可用；已返回的数据会先展示。</p> : null}
    {actionError ? <p className="studio-action-error" role="alert">{actionError}</p> : null}
    <div className="studio-grid"><ListPanel title="Projects" icon={FolderKanban} data={tasks.data} empty="暂无项目任务。" /><ListPanel title="Tools" icon={Wrench} data={tools.data} empty="暂无工具定义。" /><section className="studio-panel"><div className="studio-panel-heading"><span><RadioTower size={16} aria-hidden="true" />Channels</span></div>{bindings.data?.items.length ? <div className="studio-list">{bindings.data.items.map((binding, index) => { const id = value(binding, "id"); const status = value(binding, "binding_status"); return <div className="studio-row" key={String(binding.id ?? index)}><div><strong>{itemTitle(binding)}</strong><small>{value(binding, "binding_scope")} · {value(binding, "outbound_policy")} · review {value(binding, "memory_write_requires_review")}</small></div><div className="studio-row-actions"><span>{status}</span>{status === "active" ? <button type="button" onClick={() => setPendingBindingAction({ id, action: "disable" })}>停用</button> : status !== "revoked" ? <button type="button" onClick={() => setPendingBindingAction({ id, action: "activate" })}>启用</button> : null}{status !== "revoked" ? <button type="button" onClick={() => setPendingBindingAction({ id, action: "revoke" })}>撤销</button> : null}</div></div>; })}</div> : <p className="studio-empty">暂无渠道绑定。</p>}</section><ListPanel title="Discord" icon={Bot} data={discordBots} empty="暂无 Discord bot identity。" /><ListPanel title="Channel revoke" icon={ShieldCheck} data={revokes.data} empty="暂无渠道撤销记录。" /><ListPanel title="Channel audit" icon={ShieldCheck} data={audits.data} empty="暂无渠道审计记录。" /></div>
    {pendingBindingAction ? <ConfirmActionDialog title={pendingBindingAction.action === "revoke" ? "撤销渠道绑定" : pendingBindingAction.action === "disable" ? "停用渠道绑定" : "启用渠道绑定"} description={pendingBindingAction.action === "revoke" ? "撤销会阻止该绑定继续接收入站、外发、check-in 和候选生成；审计记录会保留。" : "该操作会通过既有渠道绑定接口写入状态，并刷新审计证据。"} confirmLabel="确认执行" cancelLabel="暂不执行" busy={savingBinding} onConfirm={confirmBindingAction} onCancel={() => setPendingBindingAction(null)} /> : null}
  </>;
}

function StudioSystem() {
  const providers = useStudioList("provider-configs", "/llm-provider-configs");
  const permissions = useStudioList("tool-permissions", "/tool-permissions");
  const reranker = useStudioList("reranker-runs", "/memory-reranker-runs");
  const presence = useStudioList("presence-policy-runs", "/presence-policy-runs");
  const health = useQuery({ queryKey: ["studio", "health"], queryFn: getStudioHealth, staleTime: 15_000 });
  const database = useQuery({ queryKey: ["studio", "db-health"], queryFn: getStudioDatabaseHealth, staleTime: 15_000 });
  const environment = useQuery({ queryKey: ["studio", "environment"], queryFn: getStudioEnvironment, staleTime: 15_000 });
  const gate = useQuery({ queryKey: ["studio", "activation-gate"], queryFn: getActivationGate, staleTime: 15_000 });
  const systemQueries = [providers, permissions, reranker, presence, health, database, environment, gate];
  const failed = systemQueries.every((query) => query.isError);
  const partial = systemQueries.some((query) => query.isLoading || query.isError);
  if (failed) return <DataState kind="error" title="系统状态暂不可用" description="请确认 Agent API 基线与当前 base URL。" />;
  return <>
    <section className="studio-policy-banner"><ShieldCheck size={18} aria-hidden="true" /><div><strong>Memory reranker 与 Presence bandit 均为 Shadow</strong><p>Activation gate 只显示证据和状态；不提供 active policy 控制。</p></div><span>{value(gate.data ?? {}, "status")}</span></section>
    {partial ? <p className="studio-partial-note">部分系统诊断仍在读取或暂不可用；已返回的数据会先展示。</p> : null}
    <div className="studio-diagnostics"><span><Activity size={16} aria-hidden="true" />API：{value(health.data ?? {}, "status")}</span><span><KeyRound size={16} aria-hidden="true" />数据库：{value(database.data ?? {}, "database")}</span><span><Bot size={16} aria-hidden="true" />环境：{value(environment.data ?? {}, "env")}</span><span><ShieldCheck size={16} aria-hidden="true" />Active allowed：{value(gate.data ?? {}, "active_allowed")}</span></div>
    <div className="studio-grid"><ListPanel title="Provider" icon={Bot} data={providers.data} empty="暂无 Provider 配置。" /><ListPanel title="工具权限" icon={KeyRound} data={permissions.data} empty="暂无工具权限记录。" /><ListPanel title="Memory reranker" icon={Sparkles} data={reranker.data} empty="暂无 reranker 运行记录。" /><ListPanel title="Presence policy" icon={Activity} data={presence.data} empty="暂无 Presence policy 运行记录。" /></div>
  </>;
}

export function StudioWorkspace({ area }: { area: Area }) {
  const copy = titles[area];
  return <main className="studio-workspace"><header className="studio-hero"><div><p>设置 / {copy.eyebrow.replace("Studio / ", "")}</p><h1>{copy.title}</h1><span>{copy.description}</span></div><aside><Sparkles size={18} aria-hidden="true" /><span>设置概览</span><p>这里保留可追溯的运行证据；具体功能请从左侧设置分类进入。</p></aside></header>{area === "quality" ? <StudioQuality /> : area === "integrations" ? <StudioIntegrations /> : <StudioSystem />}</main>;
}
