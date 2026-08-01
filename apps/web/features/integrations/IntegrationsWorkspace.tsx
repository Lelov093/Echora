"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bot,
  Cable,
  CircleAlert,
  ClipboardCheck,
  FolderKanban,
  GitBranch,
  History,
  Link2,
  RadioTower,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { ConfirmActionDialog } from "@/components/patterns/ConfirmActionDialog";
import { DataState } from "@/components/patterns/DataState";
import { DETAIL_PAGE_SIZE, Pagination, usePageParam } from "@/components/patterns/Pagination";
import {
  activateChannelBinding,
  applyChannelRevoke,
  bindDiscordBotToCompanion,
  disableChannelBinding,
  listChannelAuditLogs,
  listChannelBindings,
  listChannelProviders,
  listChannelRevokeEvents,
  listChannelTraceEvents,
  listDiscordBotIdentityBindings,
  listDiscordBotIdentitiesStatus,
  testDiscordBotConnection,
  unbindDiscordBot,
  type DiscordIdentityBinding,
} from "@/lib/api/channelGateway";
import { listCompanions } from "@/lib/api/companions";
import {
  completeProjectTask,
  createProjectTask,
  createProjectTaskEvidenceLink,
  listProjectMilestones,
  listProjectTasks,
} from "@/lib/api/projects";
import {
  cancelToolRun,
  confirmToolRun,
  listToolDefinitions,
  listToolPermissions,
  listToolRuns,
  retryToolRun,
  setToolPermission,
  type ToolPermissionPolicy,
  type ToolRun,
} from "@/lib/api/tools";
import type {
  ChannelProvider,
  CompanionBundle,
  ToolDefinition,
} from "@/lib/types";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";

type IntegrationView = "projects" | "tools" | "channels" | "discord" | "audit";
type Item = Record<string, unknown>;

const viewCopy: Record<IntegrationView, { eyebrow: string; title: string; description: string }> = {
  projects: { eyebrow: "Studio / Integrations", title: "项目与证据", description: "把任务、里程碑与 Trace 证据放在同一条可追溯的工作线上。" },
  tools: { eyebrow: "Studio / Integrations", title: "工具治理", description: "查看工具定义、权限要求和运行结果；每次受控执行都保留明确确认。" },
  channels: { eyebrow: "Studio / Integrations", title: "渠道绑定", description: "围绕 Companion、channel identity 与 binding 管理连接生命周期。" },
  discord: { eyebrow: "Studio / Integrations", title: "Discord 身份", description: "检查 bot readiness 与 Companion 绑定；凭据始终留在安全配置中。" },
  audit: { eyebrow: "Studio / Integrations", title: "渠道审计", description: "按 binding 查看 trace、audit 与 revoke 证据；撤销操作回到绑定详情执行。" },
};

function text(item: Item | null | undefined, key: string, fallback = "—") {
  const value = item?.[key];
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value) : fallback;
}

function shortId(value?: string | null) {
  return value ? value.slice(0, 8) : "—";
}

function riskLabel(risk: string) {
  return {
    low: "低风险",
    medium: "中等风险",
    high: "高风险",
    critical: "关键风险",
  }[risk] ?? risk;
}

function toolPurpose(name: string) {
  return ({
    web_search: "查找公开网络信息",
    web_read: "读取公开网页内容",
    weather: "查询天气",
    exchange_rate: "查询汇率",
    reminder: "创建提醒",
    calendar_event: "创建日程",
    note: "保存笔记",
  } as Record<string, string>)[name] ?? "帮助伙伴完成受控行动";
}

function redact(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redact);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) => {
    if (/token|secret|password|api[_-]?key|authorization|credential/i.test(key)) return [key, "[已隐藏]"];
    return [key, redact(item)];
  }));
}

function requestState(queries: Array<{ isPending: boolean; isError: boolean }>) {
  return {
    loading: queries.length > 0 && queries.every((query) => query.isPending),
    failed: queries.length > 0 && queries.every((query) => query.isError),
    partial: queries.some((query) => query.isPending || query.isError),
  };
}

function DetailShell({ view, children }: { view: IntegrationView; children: React.ReactNode }) {
  const copy = viewCopy[view];
  return (
    <main className="detail-workspace">
      <header className="detail-hero">
        <div>
          <p>设置 / 交互与能力</p>
          <h1>{copy.title}</h1>
          <span>{copy.description}</span>
        </div>
        <aside>
          <Cable size={18} aria-hidden="true" />
          <strong>连接仍受治理</strong>
          <p>外发、channel memory 与 revoke 沿用既有 review、audit 和 boundary gate。</p>
        </aside>
      </header>
      {children}
    </main>
  );
}

function PartialNote({ show }: { show: boolean }) {
  return show ? <p className="detail-partial-note">部分证据仍在读取或暂不可用；已返回的数据先展示。</p> : null;
}

function Panel({ title, icon: Icon, children, className = "" }: { title: string; icon: typeof Activity; children: React.ReactNode; className?: string }) {
  return <section className={`detail-panel ${className}`}><div className="detail-panel-heading"><span><Icon size={17} aria-hidden="true" />{title}</span></div>{children}</section>;
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="detail-empty">{children}</div>;
}

function ProjectsView() {
  const [tasksPage, setTasksPage] = usePageParam("tasks_page");
  const [milestonesPage, setMilestonesPage] = usePageParam("milestones_page");
  const tasksQuery = useQuery({ queryKey: ["integrations", "project-tasks", tasksPage], queryFn: () => listProjectTasks({ page: tasksPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const milestonesQuery = useQuery({ queryKey: ["integrations", "project-milestones", milestonesPage], queryFn: () => listProjectMilestones({ page: milestonesPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const [pendingAction, setPendingAction] = useState<"complete" | "evidence" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tasks = tasksQuery.data?.items ?? [];
  const milestones = milestonesQuery.data?.items ?? [];
  const selected = tasks.find((task) => task.id === selectedId) ?? tasks[0] ?? null;
  const state = requestState([tasksQuery, milestonesQuery]);

  async function refresh() {
    await Promise.all([tasksQuery.refetch(), milestonesQuery.refetch()]);
  }

  async function runAction(action: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await action(); await refresh(); setPendingAction(null); } catch (cause) { setError(cause instanceof Error ? cause.message : "项目操作失败。"); } finally { setBusy(false); }
  }

  if (state.loading) return <DataState kind="loading" title="正在读取项目证据" description="正在同步任务、里程碑与证据链接。" />;
  if (state.failed) return <DataState kind="error" title="项目数据暂不可用" description="请确认 Agent API 与当前 base URL。" />;
  return <>
    <PartialNote show={state.partial} />
    {error ? <p className="detail-error" role="alert">{error}</p> : null}
    <div className="detail-grid detail-project-grid detail-master-detail">
      <Panel title="任务流" icon={FolderKanban} className="detail-master-list">
        <form className="detail-inline-form" onSubmit={(event) => { event.preventDefault(); if (!title.trim()) return; void runAction(() => createProjectTask({ title: title.trim(), status: "todo", priority: 2 })); setTitle(""); }}>
          <label htmlFor="project-task-title">新增任务</label>
          <div><input id="project-task-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="写下一个可追溯的任务" /><button type="submit" className="detail-action detail-action-primary" disabled={!title.trim() || busy}>添加</button></div>
        </form>
        <div className="detail-record-list">
          {tasks.map((task) => <button key={task.id} type="button" className={`detail-record ${selected?.id === task.id ? "is-selected" : ""}`} onClick={() => setSelectedId(task.id)}><span><strong>{task.title}</strong><small>{task.status} · priority {task.priority ?? 0}</small></span><em>{task.evidence_summary || "待补充证据"}</em></button>)}
          {!tasks.length ? <Empty>当前没有项目任务。可以从上方创建第一条真实任务。</Empty> : null}
        </div>
        <Pagination pagination={tasksQuery.data?.pagination} page={tasksPage} onPageChange={(nextPage) => { setSelectedId(null); setTasksPage(nextPage); }} disabled={tasksQuery.isFetching} />
      </Panel>
      <Panel title="任务 Inspector" icon={History} className="detail-inspector">
        {selected ? <>
          <div className="detail-inspector-title"><strong>{selected.title}</strong><span>{selected.status}</span></div>
          <p className="detail-muted">任务 ID：{shortId(selected.id)} · 证据链接必须指向真实记录。</p>
          <div className="detail-action-row"><button type="button" className="detail-action" disabled={busy || selected.status === "completed"} onClick={() => setPendingAction("complete")}>完成任务</button><button type="button" className="detail-action" disabled={busy || !evidenceId.trim()} onClick={() => setPendingAction("evidence")}>关联证据</button></div>
          <label className="detail-field"><span>Trace / evidence ID</span><input value={evidenceId} onChange={(event) => setEvidenceId(event.target.value)} placeholder="粘贴真实证据 ID" /></label>
          <pre>{JSON.stringify(redact({ id: selected.id, status: selected.status, priority: selected.priority, evidence_summary: selected.evidence_summary }), null, 2)}</pre>
        </> : <Empty>选择一条任务查看状态与下一步。</Empty>}
      </Panel>
      <Panel title="里程碑" icon={GitBranch} className="detail-supporting-list">
        <div className="detail-record-list">
          {milestones.map((milestone) => <div key={milestone.id} className="detail-record"><span><strong>{milestone.title}</strong><small>{milestone.status} · priority {milestone.priority ?? 0}</small></span><em>{milestone.target_at || "未设目标日期"}</em></div>)}
          {!milestones.length ? <Empty>当前没有可读取的里程碑。</Empty> : null}
        </div>
        <Pagination pagination={milestonesQuery.data?.pagination} page={milestonesPage} onPageChange={setMilestonesPage} disabled={milestonesQuery.isFetching} />
      </Panel>
    </div>
    {pendingAction && selected ? <ConfirmActionDialog title={pendingAction === "complete" ? "完成这条任务？" : "关联这条证据？"} description={pendingAction === "complete" ? "完成状态会写入项目任务事件，之后仍可从事件历史追溯。" : "只会保存你提供的 evidence ID，不会生成伪造证据。"} confirmLabel="确认写入" cancelLabel="暂不执行" busy={busy} onCancel={() => setPendingAction(null)} onConfirm={() => runAction(() => pendingAction === "complete" ? completeProjectTask(selected.id) : createProjectTaskEvidenceLink(selected.id, { evidence_type: "trace", evidence_id: evidenceId.trim(), relevance_score: 1 }))} /> : null}
  </>;
}

function ToolsView() {
  const companion = useActiveCompanionContext();
  const companionId = companion.activeCompanionId;
  const [definitionsPage, setDefinitionsPage] = usePageParam("definitions_page");
  const [runsPage, setRunsPage] = usePageParam("runs_page");
  const definitionsQuery = useQuery({ queryKey: ["integrations", "tool-definitions", definitionsPage], queryFn: () => listToolDefinitions({ page: definitionsPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const runsQuery = useQuery({ queryKey: ["integrations", "tool-runs", companionId, runsPage], queryFn: () => listToolRuns({ companion_id: companionId, page: runsPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const permissionsQuery = useQuery({ queryKey: ["integrations", "tool-permissions", companionId], queryFn: () => listToolPermissions({ companion_id: companionId, page: 1, page_size: 100 }), staleTime: 15_000 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<"confirm" | "cancel" | "retry" | null>(null);
  const [pendingPolicies, setPendingPolicies] = useState<Record<string, ToolPermissionPolicy>>({});
  const [permissionBusy, setPermissionBusy] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const definitions = definitionsQuery.data?.items ?? [];
  const runs = runsQuery.data?.items ?? [];
  const selected = (runs.find((run) => run.id === selectedId) ?? runs[0] ?? null) as ToolRun | null;
  const state = requestState([definitionsQuery, runsQuery, permissionsQuery]);
  const highRisk = definitions.filter((tool) => tool.risk_level === "high" || tool.risk_level === "critical").length;
  const permissionByDefinition = new Map(
    (permissionsQuery.data?.items ?? []).map((permission) => [permission.tool_definition_id, permission]),
  );

  async function refresh() { await Promise.all([definitionsQuery.refetch(), runsQuery.refetch()]); }
  async function runAction(action: () => Promise<unknown>) { setBusy(true); setError(null); try { await action(); await refresh(); setPendingAction(null); } catch (cause) { setError(cause instanceof Error ? cause.message : "工具操作失败。"); } finally { setBusy(false); } }
  async function savePermission(toolDefinitionId: string, policy: ToolPermissionPolicy) {
    setPermissionBusy(toolDefinitionId);
    setError(null);
    try {
      await setToolPermission(toolDefinitionId, {
        companion_id: companionId,
        policy,
        reason: "user_configured_in_tools",
      });
      await permissionsQuery.refetch();
      setPendingPolicies((current) => {
        const next = { ...current };
        delete next[toolDefinitionId];
        return next;
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "工具权限保存失败；你的选择仍保留在页面中，可以重试。");
    } finally {
      setPermissionBusy(null);
    }
  }

  if (state.loading) return <DataState kind="loading" title="正在读取工具证据" description="正在同步工具定义与运行历史。" />;
  if (state.failed) return <DataState kind="error" title="工具数据暂不可用" description="请确认 Agent API 与当前 base URL。" />;
  return <>
    <PartialNote show={state.partial} />
    {error ? <p className="detail-error" role="alert">{error}</p> : null}
    <div className="detail-stat-line"><span><Wrench size={15} />{definitionsQuery.data?.pagination.total ?? definitions.length} 个工具定义</span><span><Activity size={15} />{runsQuery.data?.pagination.total ?? runs.length} 次运行</span><span><CircleAlert size={15} />本页 {highRisk} 个高风险定义</span></div>
    <div className="detail-grid detail-tool-grid detail-master-detail">
      <Panel title="运行历史" icon={Activity} className="detail-master-list">
        <div className="detail-record-list">{runs.map((run) => <button key={run.id} type="button" className={`detail-record ${selected?.id === run.id ? "is-selected" : ""}`} onClick={() => setSelectedId(run.id)}><span><strong>{run.status}</strong><small>{shortId(run.id)} · {run.risk_level}</small></span><em>{run.permission_required ? "需要权限" : "已具备权限"}</em></button>)}{!runs.length ? <Empty>当前没有工具运行。</Empty> : null}</div>
        <Pagination pagination={runsQuery.data?.pagination} page={runsPage} onPageChange={(nextPage) => { setSelectedId(null); setRunsPage(nextPage); }} disabled={runsQuery.isFetching} />
      </Panel>
      <Panel title="运行 Inspector" icon={ShieldCheck} className="detail-inspector">
        {selected ? <><div className="detail-inspector-title"><strong>{selected.status}</strong><span>{selected.permission_required ? "需要权限" : "可继续"}</span></div><p className="detail-muted">运行 ID：{shortId(selected.id)} · 所有改变状态的操作都需要明确确认。</p><div className="detail-action-row"><button type="button" className="detail-action" onClick={() => setPendingAction("confirm")} disabled={busy}>确认</button><button type="button" className="detail-action" onClick={() => setPendingAction("cancel")} disabled={busy}>取消</button><button type="button" className="detail-action" onClick={() => setPendingAction("retry")} disabled={busy}>重试</button></div><pre>{JSON.stringify(redact({ input: selected.input_json ?? {}, output: selected.output_json ?? {} }), null, 2)}</pre></> : <Empty>选择一条运行记录查看受控操作。</Empty>}
      </Panel>
      <Panel title="伙伴可用的工具" icon={Wrench} className="detail-supporting-list">
        <p className="detail-muted">权限只作用于当前伙伴。高风险写操作始终保留本次确认，不会被低风险自动使用策略绕过。</p>
        {permissionsQuery.isError ? <p className="detail-error" role="alert">当前权限真值读取失败。为避免覆盖未知状态，暂不允许保存；刷新页面后重试。</p> : null}
        <div className="detail-record-list">{definitions.map((tool: ToolDefinition) => {
          const permission = permissionByDefinition.get(tool.id);
          const savedPolicy = (permission?.policy || tool.permission_policy) as ToolPermissionPolicy;
          const selectedPolicy = pendingPolicies[tool.id] ?? savedPolicy;
          const dirty = selectedPolicy !== savedPolicy;
          return <div key={tool.id} className="detail-record detail-tool-permission-row">
            <span>
              <strong>{tool.display_name || tool.name}</strong>
              <small>{tool.description || toolPurpose(tool.name)} · {riskLabel(tool.risk_level)}</small>
            </span>
            <div className="detail-tool-permission-control">
              <select
                aria-label={`${tool.display_name || tool.name} 使用策略`}
                value={selectedPolicy}
                disabled={permissionBusy !== null || permissionsQuery.isError}
                onChange={(event) => setPendingPolicies((current) => ({
                  ...current,
                  [tool.id]: event.target.value as ToolPermissionPolicy,
                }))}
              >
                <option value="not_required">允许低风险自动使用</option>
                <option value="ask_once">首次使用时询问</option>
                <option value="ask_every_time">每次使用都询问</option>
                <option value="disabled">禁用</option>
              </select>
              <button
                type="button"
                className="detail-action"
                disabled={!dirty || permissionBusy !== null || permissionsQuery.isError}
                onClick={() => void savePermission(tool.id, selectedPolicy)}
              >
                {permissionBusy === tool.id ? "保存中…" : "保存"}
              </button>
            </div>
          </div>;
        })}{!definitions.length ? <Empty>当前没有工具定义。</Empty> : null}</div>
        <Pagination pagination={definitionsQuery.data?.pagination} page={definitionsPage} onPageChange={setDefinitionsPage} disabled={definitionsQuery.isFetching} />
      </Panel>
    </div>
    {pendingAction && selected ? <ConfirmActionDialog title={`${pendingAction === "confirm" ? "确认" : pendingAction === "cancel" ? "取消" : "重试"}这次工具运行？`} description="操作会通过工具领域 API 写入运行状态，并保留可追溯记录。" confirmLabel="确认执行" cancelLabel="暂不执行" busy={busy} onCancel={() => setPendingAction(null)} onConfirm={() => runAction(() => {
      const scope = { companion_id: companionId, conversation_id: selected.conversation_id };
      return pendingAction === "confirm" ? confirmToolRun(selected.id, scope) : pendingAction === "cancel" ? cancelToolRun(selected.id, scope) : retryToolRun(selected.id, scope);
    })} /> : null}
  </>;
}

function ChannelsView({ focus }: { focus?: string }) {
  const isRevokeHistory = focus === "revoke";
  const [bindingsPage, setBindingsPage] = usePageParam("bindings_page");
  const [providersPage, setProvidersPage] = usePageParam("providers_page");
  const [revokesPage, setRevokesPage] = usePageParam("revokes_page");
  const providersQuery = useQuery({ queryKey: ["integrations", "channel-providers", providersPage], queryFn: () => listChannelProviders({ page: providersPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000, enabled: !isRevokeHistory });
  const bindingsQuery = useQuery({ queryKey: ["integrations", "channel-bindings", bindingsPage], queryFn: () => listChannelBindings({ page: bindingsPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000, enabled: !isRevokeHistory });
  const auditsQuery = useQuery({ queryKey: ["integrations", "channel-audits-count"], queryFn: () => listChannelAuditLogs({ page: 1, page_size: 1 }), staleTime: 15_000, enabled: !isRevokeHistory });
  const revokesQuery = useQuery({ queryKey: ["integrations", "channel-revokes", revokesPage], queryFn: () => listChannelRevokeEvents({ page: revokesPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<"activate" | "disable" | "revoke" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bindings = bindingsQuery.data?.items ?? [];
  const providers = providersQuery.data?.items ?? [];
  const audits = auditsQuery.data?.items ?? [];
  const revokes = revokesQuery.data?.items ?? [];
  const selected = bindings.find((binding) => binding.id === selectedId) ?? bindings[0] ?? null;
  const state = requestState(isRevokeHistory ? [revokesQuery] : [providersQuery, bindingsQuery, auditsQuery, revokesQuery]);

  async function refresh() { await Promise.all([providersQuery.refetch(), bindingsQuery.refetch(), auditsQuery.refetch(), revokesQuery.refetch()]); }
  async function runAction(action: () => Promise<unknown>) { setBusy(true); setError(null); try { await action(); await refresh(); setPendingAction(null); } catch (cause) { setError(cause instanceof Error ? cause.message : "渠道操作失败。"); } finally { setBusy(false); } }

  if (state.loading) return <DataState kind="loading" title="正在读取渠道关系" description="正在同步 Provider、binding、audit 与 revoke 证据。" />;
  if (state.failed) return <DataState kind="error" title="渠道数据暂不可用" description="请确认 Agent API 与当前 base URL。" />;
  return <>
    <PartialNote show={state.partial} />
    {error ? <p className="detail-error" role="alert">{error}</p> : null}
    <nav className="channel-owner-tabs" aria-label="Channels 内部视图">
      <Link href="/settings/channels" aria-current={!isRevokeHistory ? "page" : undefined}>Binding 管理</Link>
      <Link href="/settings/channels?view=revoke" aria-current={isRevokeHistory ? "page" : undefined}>撤销历史</Link>
    </nav>
    {isRevokeHistory ? <Panel title="撤销历史" icon={ShieldCheck} className="detail-supporting-list">
      <div className="detail-record-list">{revokes.map((event) => <div key={event.id} className="detail-record"><span><strong>{event.revoke_status} · {event.revoke_scope}</strong><small>binding {shortId(event.channel_binding_id)} · {event.revoke_reason || "未记录原因"}</small></span><em>{event.applied_at || "—"}</em></div>)}{!revokes.length ? <Empty>当前没有撤销记录；撤销只在 Binding 管理的详情中执行并保留审计。</Empty> : null}</div>
      <Pagination pagination={revokesQuery.data?.pagination} page={revokesPage} onPageChange={setRevokesPage} disabled={revokesQuery.isFetching} />
    </Panel> : <>
    <div className="detail-stat-line"><span><Cable size={15} />{providersQuery.data?.pagination.total ?? providers.length} 个 Provider</span><span><Link2 size={15} />{bindingsQuery.data?.pagination.total ?? bindings.length} 个 binding</span><span><History size={15} />{auditsQuery.data?.pagination.total ?? audits.length} 条审计</span><span><ShieldCheck size={15} />{revokesQuery.data?.pagination.total ?? revokes.length} 条撤销</span></div>
    <div className="detail-grid detail-channel-grid detail-master-detail">
      <Panel title="Binding 关系" icon={Link2} className="detail-master-list">
        <div className="detail-record-list">{bindings.map((binding) => <button key={binding.id} type="button" className={`detail-record ${selected?.id === binding.id ? "is-selected" : ""}`} onClick={() => setSelectedId(binding.id)}><span><strong>{binding.provider?.provider_display_name || shortId(binding.provider_id)}</strong><small>Companion {shortId(binding.companion_id)} · {binding.binding_scope}</small></span><em>{binding.binding_status}</em></button>)}{!bindings.length ? <Empty>当前没有渠道绑定。新绑定仍需经过既有领域流程创建。</Empty> : null}</div>
        <Pagination pagination={bindingsQuery.data?.pagination} page={bindingsPage} onPageChange={(nextPage) => { setSelectedId(null); setBindingsPage(nextPage); }} disabled={bindingsQuery.isFetching} />
      </Panel>
      <Panel title="Binding Inspector" icon={ClipboardCheck} className="detail-inspector">
        {selected ? <><div className="detail-inspector-title"><strong>{selected.provider?.provider_display_name || "Channel binding"}</strong><span>{selected.binding_status}</span></div><p className="detail-muted">binding {shortId(selected.id)} · Companion {shortId(selected.companion_id)}</p><div className="detail-chip-row"><span>inbound {String(selected.can_receive_inbound)}</span><span>outbound {String(selected.can_send_outbound)}</span><span>memory review {String(selected.memory_write_requires_review)}</span><span>raw payload {String(selected.raw_message_storage_allowed)}</span></div><div className="detail-action-row"><button type="button" className="detail-action" onClick={() => setPendingAction("activate")} disabled={busy || selected.binding_status === "active" || selected.binding_status === "revoked"}>启用</button><button type="button" className="detail-action" onClick={() => setPendingAction("disable")} disabled={busy || selected.binding_status === "disabled" || selected.binding_status === "revoked"}>停用</button><button type="button" className="detail-action detail-action-danger" onClick={() => setPendingAction("revoke")} disabled={busy || selected.binding_status === "revoked"}>撤销</button></div><p className="detail-muted">撤销会阻止 inbound、outbound、check-in 与候选生成；不会删除审计历史。</p><pre>{JSON.stringify(redact({ id: selected.id, binding_scope: selected.binding_scope, permission_scope: selected.permission_scope, outbound_policy: selected.outbound_policy, memory_policy: selected.memory_policy, provider_id: selected.provider_id }), null, 2)}</pre></> : <Empty>选择一条 binding 查看治理边界。</Empty>}
      </Panel>
      <Panel title="Provider 与边界" icon={RadioTower} className="detail-supporting-list">
        <div className="detail-record-list">{providers.map((provider: ChannelProvider) => <div key={provider.id} className="detail-record"><span><strong>{provider.provider_display_name}</strong><small>{provider.provider_key} · {provider.is_real_provider ? "真实 provider" : "契约 provider"}</small></span><em>{provider.provider_status}</em></div>)}{!providers.length ? <Empty>当前没有渠道 Provider。</Empty> : null}</div><Pagination pagination={providersQuery.data?.pagination} page={providersPage} onPageChange={setProvidersPage} disabled={providersQuery.isFetching} />
      </Panel>
    </div>
    {pendingAction && selected ? <ConfirmActionDialog title={`${pendingAction === "revoke" ? "撤销" : pendingAction === "disable" ? "停用" : "启用"}这条 binding？`} description={pendingAction === "revoke" ? "撤销会立即停止该 binding 的入站、外发、check-in 和候选生成，且保留 revoke 与 audit 证据。" : "状态变化会通过 channel gateway API 写入，并刷新审计证据。"} confirmLabel="确认写入" cancelLabel="暂不执行" busy={busy} onCancel={() => setPendingAction(null)} onConfirm={() => runAction(() => pendingAction === "activate" ? activateChannelBinding(selected.id, { reason: "integrations_confirmed" }) : pendingAction === "disable" ? disableChannelBinding(selected.id, { reason: "integrations_confirmed" }) : applyChannelRevoke(selected.id, { reason: "integrations_confirmed" }))} /> : null}
    </>}
  </>;
}

function DiscordView() {
  const statusQuery = useQuery({ queryKey: ["integrations", "discord-status"], queryFn: listDiscordBotIdentitiesStatus, staleTime: 15_000 });
  const bindingsQuery = useQuery({ queryKey: ["integrations", "discord-bindings"], queryFn: listDiscordBotIdentityBindings, staleTime: 15_000 });
  const companionsQuery = useQuery({ queryKey: ["integrations", "companions"], queryFn: () => listCompanions({ page_size: 50 }), staleTime: 15_000 });
  const [pendingBind, setPendingBind] = useState<{ botKey: string; companionId: string } | null>(null);
  const [pendingUnbind, setPendingUnbind] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bots = statusQuery.data?.bots ?? [];
  const bindingRows = bindingsQuery.data?.bots ?? [];
  const companions = companionsQuery.data?.items ?? [];
  const state = requestState([statusQuery, bindingsQuery, companionsQuery]);

  async function reload() { await Promise.all([statusQuery.refetch(), bindingsQuery.refetch()]); }
  async function test(botKey: string) { setTesting(botKey); setError(null); try { const result = await testDiscordBotConnection({ bot_key: botKey }); setMessage(`${botKey}：${text(result as Item, "connection_status", "已返回结果")}`); } catch (cause) { setError(cause instanceof Error ? cause.message : "Discord 连接测试失败。"); } finally { setTesting(null); } }
  async function bind() { if (!pendingBind) return; setError(null); try { await bindDiscordBotToCompanion({ bot_key: pendingBind.botKey, companion_id: pendingBind.companionId }); await reload(); setMessage("Discord identity 已更新绑定。"); setPendingBind(null); } catch (cause) { setError(cause instanceof Error ? cause.message : "Discord 绑定失败。"); } }
  async function unbind() { if (!pendingUnbind) return; setError(null); try { await unbindDiscordBot(pendingUnbind); await reload(); setMessage("Discord identity 已解除绑定，历史记录保留。"); setPendingUnbind(null); } catch (cause) { setError(cause instanceof Error ? cause.message : "Discord 解除绑定失败。"); } }

  if (state.loading) return <DataState kind="loading" title="正在读取 Discord readiness" description="正在同步 registry、identity 与 Companion binding。" />;
  if (state.failed) return <DataState kind="error" title="Discord 状态暂不可用" description="请确认 registry 与 Agent API 基线。" />;
  return <>
    <PartialNote show={state.partial} />
    {error ? <p className="detail-error" role="alert">{error}</p> : null}
    {message ? <p className="detail-success" role="status">{message}</p> : null}
    <section className="detail-readiness"><div><strong>凭据安全</strong><span>只显示 readiness、identity 与 binding 摘要，不渲染 token、public key 或 secret。</span></div><span className="detail-status-pill">{statusQuery.data?.registry_status || "未返回"}</span></section>
    <div className="detail-discord-grid">{bots.map((bot) => { const binding = bindingRows.find((row: DiscordIdentityBinding) => row.bot_key === bot.bot_key)?.binding; const boundId = binding?.companion_id || bot.companion_id || ""; return <Panel key={bot.bot_key} title={bot.bot_display_name || bot.bot_key} icon={Bot}><div className="detail-discord-meta"><span>registry {bot.enabled ? "enabled" : "disabled"}</span><span>token {bot.token_status}</span><span>connection {bot.connection_status || "未测试"}</span><span>Companion {boundId ? shortId(boundId) : "未绑定"}</span></div><div className="detail-action-row"><button type="button" className="detail-action" onClick={() => void test(bot.bot_key)} disabled={testing === bot.bot_key}>{testing === bot.bot_key ? "测试中…" : "测试连接"}</button><select aria-label={`${bot.bot_key} 绑定 Companion`} value={boundId} onChange={(event) => event.target.value && setPendingBind({ botKey: bot.bot_key, companionId: event.target.value })}><option value="">选择 Companion</option>{companions.map((companion: CompanionBundle) => <option key={companion.id} value={companion.id}>{companion.name}</option>)}</select>{binding?.companion_id && bot.provider_bot_id ? <button type="button" className="detail-action detail-action-danger" onClick={() => setPendingUnbind(bot.provider_bot_id || null)}>解除绑定</button> : null}</div><p className="detail-muted">每个 bot identity 只能绑定到明确 Companion；未绑定时不应路由外部消息。</p></Panel>; })}{!bots.length ? <Empty>没有发现 Discord registry identity。</Empty> : null}</div>
    {pendingBind ? <ConfirmActionDialog title="更新 Discord Companion 绑定？" description="绑定会写入 channel identity 关系；不会展示或复制任何凭据。" confirmLabel="确认绑定" cancelLabel="暂不执行" onCancel={() => setPendingBind(null)} onConfirm={bind} /> : null}
    {pendingUnbind ? <ConfirmActionDialog title="解除 Discord 绑定？" description="解除后该 identity 不再路由到 Companion，但历史审计记录会保留。" confirmLabel="确认解除" cancelLabel="暂不执行" onCancel={() => setPendingUnbind(null)} onConfirm={unbind} /> : null}
  </>;
}

function AuditView() {
  const [tracesPage, setTracesPage] = usePageParam("traces_page");
  const [auditsPage, setAuditsPage] = usePageParam("audits_page");
  const [revokesPage, setRevokesPage] = usePageParam("revokes_page");
  const tracesQuery = useQuery({ queryKey: ["integrations", "channel-traces", tracesPage], queryFn: () => listChannelTraceEvents({ page: tracesPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const auditsQuery = useQuery({ queryKey: ["integrations", "channel-audits-detail", auditsPage], queryFn: () => listChannelAuditLogs({ page: auditsPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const revokesQuery = useQuery({ queryKey: ["integrations", "channel-revokes-detail", revokesPage], queryFn: () => listChannelRevokeEvents({ page: revokesPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const state = requestState([tracesQuery, auditsQuery, revokesQuery]);
  if (state.loading) return <DataState kind="loading" title="正在读取渠道审计" description="正在同步 trace、audit 与 revoke 事件。" />;
  if (state.failed) return <DataState kind="error" title="渠道审计暂不可用" description="请确认 Agent API 与当前 base URL。" />;
  const traces = tracesQuery.data?.items ?? [];
  const audits = auditsQuery.data?.items ?? [];
  const revokes = revokesQuery.data?.items ?? [];
  return <><PartialNote show={state.partial} /><div className="detail-audit-intro"><ShieldCheck size={18} aria-hidden="true" /><div><strong>审计只显示安全摘要</strong><p>原始 channel payload 不进入聚合列表；撤销操作请在左侧选择 Revoke。</p></div></div><div className="detail-grid detail-audit-grid"><Panel title="Trace 事件" icon={Activity}><AuditList items={traces as unknown as Item[]} titleKey="trace_summary" statusKey="trace_status" /><Pagination pagination={tracesQuery.data?.pagination} page={tracesPage} onPageChange={setTracesPage} disabled={tracesQuery.isFetching} /></Panel><Panel title="Audit 日志" icon={History}><AuditList items={audits as unknown as Item[]} titleKey="audit_summary" statusKey="audit_log_type" /><Pagination pagination={auditsQuery.data?.pagination} page={auditsPage} onPageChange={setAuditsPage} disabled={auditsQuery.isFetching} /></Panel><Panel title="Revoke 事件" icon={ShieldCheck}><AuditList items={revokes as unknown as Item[]} titleKey="revoke_reason" statusKey="revoke_status" /><Pagination pagination={revokesQuery.data?.pagination} page={revokesPage} onPageChange={setRevokesPage} disabled={revokesQuery.isFetching} /></Panel></div></>;
}

function AuditList({ items, titleKey, statusKey }: { items: Item[]; titleKey: string; statusKey: string }) {
  return <div className="detail-record-list">{items.map((item, index) => <div key={String(item.id ?? index)} className="detail-record"><span><strong>{text(item, titleKey, "安全事件")}</strong><small>binding {shortId(text(item, "channel_binding_id", ""))} · {text(item, "occurred_at", text(item, "applied_at"))}</small></span><em>{text(item, statusKey)}</em></div>)}{!items.length ? <Empty>暂无记录。</Empty> : null}</div>;
}

export function IntegrationsWorkspace({ view, focus }: { view: IntegrationView; focus?: string }) {
  return <DetailShell view={view}>{view === "projects" ? <ProjectsView /> : view === "tools" ? <ToolsView /> : view === "channels" ? <ChannelsView focus={focus} /> : view === "discord" ? <DiscordView /> : <AuditView />}</DetailShell>;
}
