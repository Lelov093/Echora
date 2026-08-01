"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Gauge,
  KeyRound,
  LockKeyhole,
  ServerCog,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { ScopedHardStopControl } from "@/components/hard-stop/ScopedHardStopControl";
import { ConfirmActionDialog } from "@/components/patterns/ConfirmActionDialog";
import { DataState } from "@/components/patterns/DataState";
import { DETAIL_PAGE_SIZE, Pagination, usePageParam } from "@/components/patterns/Pagination";
import { getActivationGate, getStudioDatabaseHealth, getStudioEnvironment, getStudioHealth } from "@/lib/api/studio";
import {
  createCompanionDeletionRequest,
  dryRunDataRights,
  executeCompanionDeletionRequest,
  exportCompanionData,
  getCompanionDeletionRequest,
  getDeletionRequest,
  getReliabilityDiagnostics,
  restoreCompanionDeletionRequest,
  type CompanionDeletionRequest,
  type DataRightsOperation,
} from "@/lib/api/reliability";
import { getRuntimeConfiguration } from "@/lib/api/runtimeConfiguration";
import { listMemoryRerankerRuns, listPresencePolicyRuns } from "@/lib/api/strategy";
import { listToolDefinitions, listToolPermissions, updateToolPermission } from "@/lib/api/tools";
import { useRealtimeCoPresence } from "@/lib/hooks/useRealtimeCoPresence";
import type { ToolDefinition } from "@/lib/types";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";
import { RuntimeConfigurationWorkspace } from "@/features/system/RuntimeConfigurationWorkspace";
import {
  CompanionDeletionDialog,
  type CompanionDeletionChoice,
} from "@/features/system/CompanionDeletionDialog";

type SystemView = "overview" | "provider" | "permissions" | "diagnostics" | "data-privacy" | "policy" | "reranker" | "presence";
type Item = Record<string, unknown>;

const copy: Record<SystemView, { eyebrow: string; title: string; description: string }> = {
  overview: { eyebrow: "设置 / 系统", title: "系统状态", description: "查看 Echora 的关键连接是否就绪，并在出现问题时找到对应的修复入口。" },
  provider: { eyebrow: "设置 / 系统", title: "模型与连接", description: "配置数据库、LLM、Embedding 与 Discord 连接；本地凭据可替换或清除，但永不回显。" },
  permissions: { eyebrow: "设置 / 系统", title: "工具权限与边界", description: "工具权限按定义治理；实时边界仍保持在具体伙伴与会话范围内。" },
  diagnostics: { eyebrow: "设置 / 系统", title: "系统状态", description: "优先呈现影响使用的连接状态与修复入口；工程证据收纳在高级信息中。" },
  "data-privacy": { eyebrow: "设置 / 控制与隐私", title: "数据与隐私", description: "了解数据如何保留，并在真正执行前核对归档、遗忘、导出与永久删除的影响。" },
  policy: { eyebrow: "设置 / 高级", title: "策略运行证据", description: "供排查与验证使用；日常体验设置仍在自动化页面完成。" },
  reranker: { eyebrow: "设置 / 高级", title: "记忆调用运行证据", description: "用于核对记忆调用策略的运行结果，不承担日常设置功能。" },
  presence: { eyebrow: "设置 / 高级", title: "主动陪伴运行证据", description: "用于核对主动陪伴策略的运行结果；安静时段、专注模式与有意义的沉默始终优先。" },
};

function value(item: Item | null | undefined, key: string, fallback = "—") {
  const raw = item?.[key];
  return typeof raw === "string" || typeof raw === "number" || typeof raw === "boolean" ? String(raw) : fallback;
}

function state(queries: Array<{ isPending: boolean; isError: boolean }>) {
  return { loading: queries.length > 0 && queries.every((query) => query.isPending), failed: queries.length > 0 && queries.every((query) => query.isError), partial: queries.some((query) => query.isPending || query.isError) };
}

function Shell({ view, children }: { view: SystemView; children: React.ReactNode }) {
  const evidenceView = view === "policy" || view === "reranker" || view === "presence";
  return <main className="detail-workspace detail-system-workspace"><header className="detail-hero"><div><p>{copy[view].eyebrow}</p><h1>{copy[view].title}</h1><span>{copy[view].description}</span></div><aside><ShieldCheck size={18} aria-hidden="true" /><strong>{evidenceView ? "高级信息，不影响当前体验" : "先解决影响使用的问题"}</strong><p>{evidenceView ? "策略运行记录用于解释与排查；功能模式由自动化设置统一管理。" : "这里不展示消息、记忆正文、Prompt 或工具载荷，只呈现连接健康与可操作问题。"}</p></aside></header>{children}</main>;
}

function Partial({ show }: { show: boolean }) { return show ? <p className="detail-partial-note">部分系统证据仍在读取或暂不可用；已返回的状态先展示。</p> : null; }

function Panel({ title, icon: Icon, children, className = "" }: { title: string; icon: typeof Activity; children: React.ReactNode; className?: string }) { return <section className={`detail-panel ${className}`}><div className="detail-panel-heading"><span><Icon size={17} aria-hidden="true" />{title}</span></div>{children}</section>; }

function Empty({ children }: { children: React.ReactNode }) { return <div className="detail-empty">{children}</div>; }

function ProviderView() {
  return <RuntimeConfigurationWorkspace />;
}

const RETENTION_LAYERS = [
  { state: "使用中", scope: "对话、伙伴档案、已确认记忆与成长", retention: "由你持续保留", recovery: "可编辑、归档或按领域遗忘" },
  { state: "已归档", scope: "伙伴与 Conversation", retention: "长期保留但退出日常列表", recovery: "可恢复" },
  { state: "临时数据", scope: "候选、缓冲与未完成运行", retention: "按领域短期保留", recovery: "过期后不保证恢复" },
  { state: "已遗忘", scope: "指定记忆及其可用投影", retention: "不再进入伙伴上下文", recovery: "保留最小安全事件，不恢复正文" },
  { state: "回收区", scope: "伙伴与其私有依赖数据", retention: "保留 30 天并停止伙伴活动", recovery: "到期前可恢复" },
  { state: "永久删除", scope: "当前伙伴、私有内容、索引与缓存", retention: "仅保留不含正文的最小删除凭证", recovery: "执行开始后不可恢复" },
] as const;

const LAST_DELETION_REQUEST_KEY = "echora:last-companion-deletion-request";
const deletionCountLabels: Record<string, string> = {
  conversations: "对话",
  messages: "消息",
  private_memories: "伙伴记忆",
  channel_bindings: "渠道绑定",
  tool_runs: "工具运行",
};

function readableDeletionStatus(request: CompanionDeletionRequest) {
  if (request.status === "trash") return "回收区";
  if (request.status === "purging") return "正在永久删除";
  if (request.status === "completed") return "已永久删除";
  if (request.status === "restored") return "已恢复";
  return "删除已暂停";
}

function formatLocalDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("zh-CN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
}

function DataPrivacyView() {
  const companion = useActiveCompanionContext();
  const companionId = companion.activeCompanionId;
  const [operation, setOperation] = useState<DataRightsOperation>("archive_companion");
  const [memoryTargetId, setMemoryTargetId] = useState("");
  const [deletionDialogOpen, setDeletionDialogOpen] = useState(false);
  const [trackedRequestId, setTrackedRequestId] = useState<string | null>(() =>
    typeof window === "undefined"
      ? null
      : window.localStorage.getItem(LAST_DELETION_REQUEST_KEY),
  );
  const [deletionResult, setDeletionResult] =
    useState<CompanionDeletionRequest | null>(null);
  const dryRun = useMutation({ mutationFn: () => dryRunDataRights(companionId, operation, operation === "forget_memory" ? memoryTargetId.trim() : undefined) });
  const exportData = useMutation({
    mutationFn: () => exportCompanionData(companionId),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const safeName = data.companion.name
        .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
        .slice(0, 80);
      anchor.href = url;
      anchor.download = `echora-${safeName || "companion"}-${data.exported_at.slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    },
  });

  const companionDeletion = useQuery({
    queryKey: ["data-rights", "deletion", "companion", companionId],
    queryFn: () => getCompanionDeletionRequest(companionId),
    enabled: Boolean(companionId),
    staleTime: 5_000,
  });
  const trackedDeletion = useQuery({
    queryKey: ["data-rights", "deletion", "request", trackedRequestId],
    queryFn: () => getDeletionRequest(trackedRequestId ?? ""),
    enabled: Boolean(trackedRequestId),
    staleTime: 5_000,
    refetchInterval: (query) =>
      query.state.data?.status === "purging" ? 3_000 : false,
  });
  const currentDeletion =
    deletionResult ?? trackedDeletion.data ?? companionDeletion.data ?? null;

  useEffect(() => {
    const request = companionDeletion.data;
    if (!request || request.status === "restored") return;
    window.localStorage.setItem(LAST_DELETION_REQUEST_KEY, request.id);
  }, [companionDeletion.data]);

  useEffect(() => {
    if (!trackedDeletion.isError) return;
    window.localStorage.removeItem(LAST_DELETION_REQUEST_KEY);
  }, [trackedDeletion.isError]);

  const createDeletion = useMutation({
    mutationFn: (choice: CompanionDeletionChoice) =>
      createCompanionDeletionRequest(companionId, {
        confirmation_name: choice.confirmationName,
        skip_recovery_window: choice.skipRecoveryWindow,
        export_choice: "skip",
        idempotency_key: crypto.randomUUID(),
      }),
    onSuccess: async (request) => {
      window.localStorage.setItem(LAST_DELETION_REQUEST_KEY, request.id);
      setTrackedRequestId(request.id);
      setDeletionResult(request);
      setDeletionDialogOpen(false);
      await companion.reload();
    },
  });
  const restoreDeletion = useMutation({
    mutationFn: (requestId: string) =>
      restoreCompanionDeletionRequest(requestId),
    onSuccess: async (request) => {
      window.localStorage.removeItem(LAST_DELETION_REQUEST_KEY);
      setTrackedRequestId(null);
      setDeletionResult(request);
      await companion.reload();
    },
  });
  const retryDeletion = useMutation({
    mutationFn: (requestId: string) =>
      executeCompanionDeletionRequest(requestId),
    onSuccess: (request) => setDeletionResult(request),
  });
  const activeName =
    companion.activeCompanion?.name ??
    currentDeletion?.companion_display_name ??
    "";
  const deletionError =
    createDeletion.error instanceof Error ? createDeletion.error.message : null;
  const deletionInProgress =
    currentDeletion?.status === "trash" ||
    currentDeletion?.status === "purging" ||
    currentDeletion?.status === "failed";

  function dismissDeletionStatus() {
    window.localStorage.removeItem(LAST_DELETION_REQUEST_KEY);
    setTrackedRequestId(null);
    setDeletionResult(null);
  }

  return <>
    <section className="detail-readiness"><div><strong>你拥有当前伙伴的数据控制权</strong><span>先查看影响范围，再选择 30 天可恢复删除或立即永久删除。删除不会跨越到其他伙伴。</span></div><span className="detail-status-pill">伙伴私有范围</span></section>
    {currentDeletion ? (
      <Panel title="最近的删除操作" icon={AlertTriangle}>
        <div className="detail-inspector-title">
          <strong>
            {currentDeletion.companion_display_name
              ? `${currentDeletion.companion_display_name} · `
              : ""}
            {readableDeletionStatus(currentDeletion)}
          </strong>
          <span>{readableDeletionStatus(currentDeletion)}</span>
        </div>
        <p className="detail-muted">
          {currentDeletion.status === "trash"
            ? `将在 ${formatLocalDate(currentDeletion.purge_after)} 后自动永久删除。在此之前，你可以恢复这位伙伴。`
            : currentDeletion.status === "failed"
              ? "删除在安全边界内暂停，尚未被标记为完成。你可以重试，已删除的内容不会被恢复。"
              : currentDeletion.status === "completed"
                ? `伙伴私有内容已清除。仅保留不含正文的删除凭证；备份清理期限为 ${formatLocalDate(currentDeletion.backup_delete_due_at)}。`
                : currentDeletion.status === "restored"
                  ? "伙伴已恢复；删除期间已取消的外发与运行任务不会自动重放。"
                  : "永久删除正在按依赖范围逐步执行。"}
        </p>
        <div className="detail-action-row">
          {currentDeletion.can_restore ? (
            <button
              type="button"
              className="detail-action"
              disabled={restoreDeletion.isPending}
              onClick={() => restoreDeletion.mutate(currentDeletion.id)}
            >
              {restoreDeletion.isPending ? "正在恢复…" : "恢复伙伴"}
            </button>
          ) : null}
          {currentDeletion.can_retry ? (
            <button
              type="button"
              className="detail-action detail-action-danger"
              disabled={retryDeletion.isPending}
              onClick={() => retryDeletion.mutate(currentDeletion.id)}
            >
              {retryDeletion.isPending ? "正在继续…" : "继续永久删除"}
            </button>
          ) : null}
          {currentDeletion.status === "completed" ||
          currentDeletion.status === "restored" ? (
            <button
              type="button"
              className="detail-action"
              onClick={dismissDeletionStatus}
            >
              关闭此状态
            </button>
          ) : null}
        </div>
        {restoreDeletion.isError || retryDeletion.isError ? (
          <p className="detail-error" role="alert">
            {(restoreDeletion.error instanceof Error &&
              restoreDeletion.error.message) ||
              (retryDeletion.error instanceof Error &&
                retryDeletion.error.message) ||
              "操作失败，请重试。"}
          </p>
        ) : null}
      </Panel>
    ) : null}
    <Panel title="数据保留层级" icon={ShieldCheck}>
      <div className="detail-record-list">{RETENTION_LAYERS.map((layer) => <div key={layer.state} className="detail-record"><span><strong>{layer.state}</strong><small>{layer.scope} · {layer.retention}</small></span><em>{layer.recovery}</em></div>)}</div>
    </Panel>
    <div className="detail-grid detail-boundary-grid">
      <Panel title="执行前影响预检" icon={AlertTriangle}>
        <p className="detail-muted">选择你想进行的操作。影响预检本身不会修改数据；具备真实执行入口的操作会在结果区单独显示确认按钮。</p>
        <label className="detail-field"><span>想进行的操作</span><span className="detail-action-row"><select value={operation} onChange={(event) => { setOperation(event.target.value as DataRightsOperation); dryRun.reset(); exportData.reset(); }}><option value="archive_companion">归档伙伴</option><option value="forget_memory">遗忘一条记忆</option><option value="revoke_channels">撤销渠道绑定</option><option value="disconnect_channels">断开渠道</option><option value="export">导出伙伴数据</option><option value="permanent_delete">永久删除伙伴数据</option></select></span></label>
        {operation === "forget_memory" ? <label className="detail-field"><span>记忆 ID（必须属于当前伙伴）</span><input value={memoryTargetId} onChange={(event) => { setMemoryTargetId(event.target.value); dryRun.reset(); }} placeholder="输入记忆 ID" autoComplete="off" /></label> : null}
        <div className="detail-action-row"><button type="button" className="detail-action" disabled={!companionId || dryRun.isPending || (operation === "forget_memory" && !memoryTargetId.trim())} onClick={() => dryRun.mutate()}>{dryRun.isPending ? "正在核算…" : "查看影响范围"}</button></div>
        {dryRun.isError ? <p className="detail-error" role="alert">{dryRun.error instanceof Error ? dryRun.error.message : "预检失败"}</p> : null}
      </Panel>
      <Panel title="影响结果" icon={LockKeyhole}>{dryRun.data ? <><div className="detail-inspector-title"><strong>{dryRun.data.effect_summary}</strong><span>{dryRun.data.ready_for_explicit_execution ? "可以继续" : "尚不可执行"}</span></div><div className="detail-diagnostic-rows">{Object.entries(dryRun.data.affected_counts).map(([key, count]) => <span key={key}><strong>{deletionCountLabels[key] ?? key}</strong>{count}</span>)}</div>{dryRun.data.blockers.length ? <div className="detail-rule-list">{dryRun.data.blockers.map((blocker) => <span key={blocker}>{blocker}</span>)}</div> : null}{operation === "export" && dryRun.data.ready_for_explicit_execution ? <div className="detail-action-row"><button type="button" className="detail-action" disabled={exportData.isPending} onClick={() => exportData.mutate()}>{exportData.isPending ? "正在准备副本…" : "下载数据副本"}</button></div> : null}{operation === "permanent_delete" && dryRun.data.ready_for_explicit_execution && !deletionInProgress ? <div className="detail-action-row"><button type="button" className="detail-action detail-action-danger" disabled={!activeName} onClick={() => { createDeletion.reset(); setDeletionDialogOpen(true); }}>选择删除方式</button></div> : null}{exportData.isSuccess ? <p className="detail-success" role="status">数据副本已开始下载；文件只保存在你的浏览器下载目录。</p> : null}{exportData.isError ? <p className="detail-error" role="alert">{exportData.error instanceof Error ? exportData.error.message : "导出失败，请重试。"}</p> : null}</> : <Empty>完成预检后，这里会显示当前伙伴范围内受影响的数据和阻塞条件。</Empty>}</Panel>
    </div>
    {deletionDialogOpen && activeName ? (
      <CompanionDeletionDialog
        companionName={activeName}
        affectedCounts={dryRun.data?.affected_counts ?? {}}
        busy={createDeletion.isPending}
        error={deletionError}
        onCancel={() => {
          if (!createDeletion.isPending) setDeletionDialogOpen(false);
        }}
        onConfirm={(choice) => createDeletion.mutate(choice)}
      />
    ) : null}
  </>;
}

function PermissionView() {
  const companion = useActiveCompanionContext();
  const companionId = companion.activeCompanionId;
  const [page, setPage] = usePageParam();
  const definitionsQuery = useQuery({ queryKey: ["system", "permission-definitions"], queryFn: () => listToolDefinitions({ page_size: 100 }), staleTime: 15_000 });
  const permissionsQuery = useQuery({ queryKey: ["system", "permissions", companionId, page], queryFn: () => listToolPermissions({ companion_id: companionId, page, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const sessions = useRealtimeCoPresence({ page_size: 10 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pending, setPending] = useState<{ id: string; policy: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const definitions = definitionsQuery.data?.items ?? [];
  const permissions = permissionsQuery.data?.items ?? [];
  const selectedPermission = permissions.find((permission) => permission.id === selectedId) ?? permissions[0] ?? null;
  const selectedSession = sessions.items[0] ?? null;
  const currentState = state([definitionsQuery, permissionsQuery]);
  const definitionName = new Map(definitions.map((definition: ToolDefinition) => [definition.id, definition.display_name || definition.name]));
  async function savePermission() { if (!pending) return; setBusy(true); setError(null); try { await updateToolPermission(pending.id, { companion_id: companionId, policy: pending.policy as "not_required" | "ask_once" | "ask_every_time" | "disabled" }); await permissionsQuery.refetch(); setPending(null); } catch (cause) { setError(cause instanceof Error ? cause.message : "权限更新失败。"); } finally { setBusy(false); } }
  if (currentState.loading && sessions.loading) return <DataState kind="loading" title="正在读取权限边界" description="正在同步工具权限与 realtime session 快照。" />;
  if (currentState.failed && sessions.error) return <DataState kind="error" title="权限状态暂不可用" description="请确认 Agent API 与当前 base URL。" />;
  return <>
    <Partial show={currentState.partial || sessions.loading || Boolean(sessions.error)} />
    {error ? <p className="detail-error" role="alert">{error}</p> : null}
    <div className="detail-grid detail-master-detail">
      <Panel title="工具权限" icon={KeyRound} className="detail-master-list">
        <div className="detail-record-list">{permissions.map((permission) => <button key={permission.id} type="button" className={`detail-record ${selectedPermission?.id === permission.id ? "is-selected" : ""}`} onClick={() => setSelectedId(permission.id)}><span><strong>{definitionName.get(permission.tool_definition_id) || `工具 ${permission.tool_definition_id.slice(0, 8)}`}</strong><small>permission {permission.policy} · status {permission.status}</small></span><em>{permission.policy}</em></button>)}{!permissions.length ? <Empty>当前没有工具权限记录。</Empty> : null}</div>
        <Pagination pagination={permissionsQuery.data?.pagination} page={page} onPageChange={(nextPage) => { setSelectedId(null); setPage(nextPage); }} disabled={permissionsQuery.isFetching} />
      </Panel>
      <Panel title="权限 Inspector" icon={KeyRound} className="detail-inspector">
        {selectedPermission ? <><div className="detail-inspector-title"><strong>{definitionName.get(selectedPermission.tool_definition_id) || "工具权限"}</strong><span>{selectedPermission.status}</span></div><p className="detail-muted">当前策略：{selectedPermission.policy}。修改只作用于当前 Companion 的该工具定义，不改变 realtime speaker/listen 权限。</p><div className="detail-action-row"><button type="button" className="detail-action" onClick={() => setPending({ id: selectedPermission.id, policy: selectedPermission.policy === "disabled" ? "ask_once" : "disabled" })}>{selectedPermission.policy === "disabled" ? "改为 ask_once" : "停用此工具"}</button></div></> : <Empty>选择一条工具权限查看治理动作。</Empty>}
      </Panel>
    </div>
    <div className="detail-grid detail-boundary-grid">
      <Panel title="Realtime Boundary" icon={LockKeyhole}><div className="detail-record-list">{selectedSession ? <><div className="detail-record"><span><strong>{selectedSession.session_title || "当前 realtime session"}</strong><small>{selectedSession.session_status} · {selectedSession.default_transport}</small></span><em>{selectedSession.participants.length} participants</em></div>{selectedSession.participants.map((participant) => <div key={participant.id} className="detail-record"><span><strong>{participant.participant_role}</strong><small>{participant.participant_type} · {participant.participant_status}</small></span><em>listen {String(participant.can_listen)} · speak {String(participant.can_speak)}</em></div>)}</> : <Empty>当前没有 realtime session 快照；hard stop 需要具体 session 或 Companion 作用域。</Empty>}</div></Panel>
      <Panel title="Scoped Hard Stop" icon={ShieldCheck}><ScopedHardStopControl userId={selectedSession?.user_id ?? ""} sessionId={selectedSession?.id} channelId={selectedSession?.channels.find((channel) => channel.is_default_event_stream)?.id ?? selectedSession?.channels[0]?.id} companionId={selectedSession?.active_companion_id ?? undefined} /></Panel>
    </div>
    {pending ? <ConfirmActionDialog title={`将工具权限改为 ${pending.policy}？`} description="权限变化会通过工具权限 API 写入；不会改变 realtime hard stop 或 Companion boundary。" confirmLabel="确认更新" cancelLabel="暂不执行" busy={busy} onCancel={() => setPending(null)} onConfirm={savePermission} /> : null}
  </>;
}

function DiagnosticsView() {
  const companion = useActiveCompanionContext();
  const companionId = companion.activeCompanionId;
  const health = useQuery({ queryKey: ["system", "health"], queryFn: getStudioHealth, staleTime: 15_000 });
  const database = useQuery({ queryKey: ["system", "db-health"], queryFn: getStudioDatabaseHealth, staleTime: 15_000 });
  const environment = useQuery({ queryKey: ["system", "environment"], queryFn: getStudioEnvironment, staleTime: 15_000 });
  const configuration = useQuery({ queryKey: ["runtime-configuration", "v1"], queryFn: getRuntimeConfiguration, staleTime: 15_000 });
  const gate = useQuery({ queryKey: ["system", "policy-readiness"], queryFn: getActivationGate, staleTime: 15_000 });
  const reliability = useQuery({ queryKey: ["system", "reliability", companionId], queryFn: () => getReliabilityDiagnostics(companionId), enabled: Boolean(companionId), staleTime: 15_000 });
  const currentState = state([health, database, environment, configuration, gate, reliability]);
  if (currentState.loading) return <DataState kind="loading" title="正在检查系统状态" description="正在确认 API、数据库、模型与 Discord 配置。" />;
  if (health.isError && database.isError && configuration.isError) return <DataState kind="error" title="无法连接 Echora 服务" description="请确认 Agent API 已在 8010 端口运行，然后刷新页面。" />;
  const diagnostic = reliability.data;
  const runtime = configuration.data;
  const apiReady = value(health.data, "status", "unavailable") === "ok";
  const databaseReady = value(database.data, "database", "unavailable") === "connected";
  const llmReady = Boolean(runtime?.llm.api_key.configured && runtime.llm.base_url && runtime.llm.model);
  const embeddingReady = Boolean(runtime?.embedding.api_key.configured && runtime.embedding.model);
  const configuredDiscordBots = runtime?.discord.bots.filter((bot) => bot.enabled !== false && bot.token.configured) ?? [];
  const discordReady = configuredDiscordBots.length > 0;
  const attentionItems = [
    !apiReady ? { label: "Agent API 不可用", detail: "对话与设置无法正常工作。", href: "/settings/system/providers", action: "检查连接配置" } : null,
    !databaseReady ? { label: "数据库未连接", detail: "伙伴、对话与记忆无法可靠保存。", href: "/settings/system/providers", action: "配置数据库" } : null,
    !llmReady ? { label: "对话模型配置不完整", detail: "伙伴无法生成真实回复。", href: "/settings/system/providers", action: "配置模型" } : null,
    !embeddingReady ? { label: "Embedding 配置不完整", detail: "长期记忆检索会受到影响。", href: "/settings/system/providers", action: "配置 Embedding" } : null,
    !discordReady ? { label: "Discord 尚未就绪", detail: "不影响 Web 对话，但 Discord 陪伴不可用。", href: "/settings/channels/discord", action: "配置 Discord" } : null,
    (diagnostic?.quality.open_bad_cases ?? 0) > 0 ? { label: "有需要关注的回复反馈", detail: `当前伙伴有 ${diagnostic?.quality.open_bad_cases} 条待处理反馈。`, href: "/settings/review", action: "查看反馈" } : null,
    (diagnostic?.safety.active_hard_stops ?? 0) > 0 ? { label: "部分陪伴活动已被停止", detail: "安全停止正在生效；这可能是你的主动选择。", href: "/settings/automation", action: "检查自动化设置" } : null,
  ].filter((item): item is NonNullable<typeof item> => item !== null);
  const overallLabel = !apiReady || !databaseReady ? "需要修复" : attentionItems.length ? "部分功能需要关注" : "运行正常";
  return <>
    <Partial show={currentState.partial} />
    <section className="detail-readiness"><div><strong>{overallLabel}</strong><span>关键连接和当前伙伴状态的本机检查结果。</span></div><span className="detail-status-pill">{attentionItems.length ? `${attentionItems.length} 项需关注` : "全部就绪"}</span></section>
    <div className="detail-diagnostic-grid">
      <Panel title="基础服务" icon={ServerCog}><div className="detail-diagnostic-rows"><span><strong>Agent API</strong>{apiReady ? "正常" : "不可用"}</span><span><strong>数据库</strong>{databaseReady ? "已连接" : "未连接"}</span></div></Panel>
      <Panel title="AI 能力" icon={Sparkles}><div className="detail-diagnostic-rows"><span><strong>对话模型</strong>{llmReady ? "已配置" : "需要配置"}</span><span><strong>长期记忆检索</strong>{embeddingReady ? "已配置" : "需要配置"}</span></div></Panel>
      <Panel title="Discord" icon={Activity}><div className="detail-diagnostic-rows"><span><strong>可用 Bot</strong>{discordReady ? `${configuredDiscordBots.length} 个` : "需要配置"}</span><span><strong>Web 对话</strong>不受 Discord 状态影响</span></div></Panel>
    </div>
    <Panel title="当前需要关注" icon={AlertTriangle}>
      <div className="detail-attention-list">
        {attentionItems.map((item) => <div key={item.label} className="detail-attention-item"><span><strong>{item.label}</strong><small>{item.detail}</small></span><Link className="detail-action" href={item.href}>{item.action}</Link></div>)}
        {!attentionItems.length ? <Empty>当前没有影响主要体验的问题。</Empty> : null}
      </div>
    </Panel>
    <details className="detail-advanced-details">
      <summary><Gauge size={17} aria-hidden="true" /><span><strong>高级诊断信息</strong><small>供故障排查与开发验证使用</small></span></summary>
      <div className="detail-grid detail-boundary-grid">
        <Panel title="运行闭环" icon={Activity}><div className="detail-record-list">{diagnostic?.runtime_domains.map((domain) => <div key={domain.key} className="detail-record"><span><strong>{domain.label}</strong><small>总计 {domain.total} · 进行中 {domain.active ?? 0} · 失败 {domain.failed ?? 0} · 卡住 {domain.stuck ?? 0}</small></span><em>{domain.status}</em></div>)}{!diagnostic?.runtime_domains.length ? <Empty>当前伙伴暂无可用运行诊断。</Empty> : null}</div></Panel>
        <Panel title="安全边界" icon={ShieldCheck}><div className="detail-diagnostic-rows"><span><strong>主动停止</strong>{diagnostic?.safety.active_hard_stops ?? "—"}</span><span><strong>跨边界待审核</strong>{diagnostic?.safety.pending_shared_reviews ?? "—"}</span><span><strong>观察者自动发言</strong>{diagnostic?.safety.observer_auto_speaker ? "允许" : "不允许"}</span></div></Panel>
        <Panel title="策略准入" icon={Gauge}><div className="detail-diagnostic-rows"><span><strong>当前稳定模式</strong>仅评估，不自动接管</span><span><strong>高风险自动决策</strong>{value(gate.data, "active_allowed") === "true" ? "已授权" : "未授权"}</span><span><strong>准入状态</strong>{value(gate.data, "status", "未报告")}</span></div></Panel>
        <Panel title="运行环境" icon={ServerCog}><div className="detail-diagnostic-rows"><span><strong>环境</strong>{value(environment.data, "env", "未报告")}</span><span><strong>后端端口</strong>{value(environment.data, "backend_port", "未报告")}</span></div></Panel>
      </div>
      <Link className="detail-shadow-policy-link" href="/settings/system/shadow-policies"><span><strong>策略运行证据</strong><small>查看记忆排序与主动陪伴策略的 Shadow 评估、准入状态和历史记录</small></span><b>打开高级页面</b></Link>
    </details>
  </>;
}

function PolicyView({ focus }: { focus?: "reranker" | "presence" }) {
  const [rerankerPage, setRerankerPage] = usePageParam("reranker_page");
  const [presencePage, setPresencePage] = usePageParam("presence_page");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const rerankerQuery = useQuery({ queryKey: ["system", "memory-policy-evidence", rerankerPage], queryFn: () => listMemoryRerankerRuns({ page: rerankerPage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const presenceQuery = useQuery({ queryKey: ["system", "presence-policy-evidence", presencePage], queryFn: () => listPresencePolicyRuns({ page: presencePage, page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const gateQuery = useQuery({ queryKey: ["system", "policy-readiness"], queryFn: getActivationGate, staleTime: 15_000 });
  const currentState = state([rerankerQuery, presenceQuery, gateQuery]);
  if (currentState.loading) return <DataState kind="loading" title="正在读取策略运行证据" description="正在同步运行记录与准入状态。" />;
  if (currentState.failed) return <DataState kind="error" title="策略证据暂不可用" description="请确认 Agent API 与当前 base URL。" />;
  const reranker = rerankerQuery.data?.items ?? [];
  const presence = presenceQuery.data?.items ?? [];
  const focusedItems = (focus === "presence" ? presence : reranker) as unknown as Item[];
  const selected = focusedItems.find((item) => value(item, "id", "") === selectedId) ?? focusedItems[0] ?? null;
  const focusedQuery = focus === "presence" ? presenceQuery : rerankerQuery;
  const focusedPage = focus === "presence" ? presencePage : rerankerPage;
  const setFocusedPage = focus === "presence" ? setPresencePage : setRerankerPage;
  return <><Partial show={currentState.partial} /><section className="detail-policy-banner"><Sparkles size={18} aria-hidden="true" /><div><strong>稳定模式运行中</strong><p>这些结果只用于评估与解释，不会自动接管伙伴的记忆调用或主动陪伴决策。</p></div><span>高级信息</span></section>{focus ? <div className="detail-grid detail-master-detail"><Panel title={focus === "presence" ? "主动陪伴记录" : "记忆调用记录"} icon={focus === "presence" ? Activity : Sparkles} className="detail-master-list"><PolicyList items={focusedItems} selectedId={value(selected, "id", "")} onSelect={setSelectedId} /><Pagination pagination={focusedQuery.data?.pagination} page={focusedPage} onPageChange={(nextPage) => { setSelectedId(null); setFocusedPage(nextPage); }} disabled={focusedQuery.isFetching} /></Panel><Panel title="运行详情" icon={ShieldCheck} className="detail-inspector">{selected ? <><div className="detail-inspector-title"><strong>{value(selected, "selected_action", value(selected, "status", "运行记录"))}</strong><span>仅供排查</span></div><p className="detail-muted">这条记录不会直接改变伙伴行为。</p><details className="detail-raw-evidence"><summary>查看原始证据</summary><pre>{JSON.stringify({ status: selected.status, learning_mode: selected.learning_mode, selected_action: selected.selected_action, reward_prediction: selected.reward_prediction, explanation: selected.explanation_json, trace_run_id: selected.trace_run_id }, null, 2)}</pre></details></> : <Empty>当前没有运行证据。</Empty>}</Panel></div> : <div className="detail-grid"><Panel title="记忆调用" icon={Sparkles}><PolicyList items={reranker as unknown as Item[]} /><Pagination pagination={rerankerQuery.data?.pagination} page={rerankerPage} onPageChange={setRerankerPage} disabled={rerankerQuery.isFetching} /></Panel><Panel title="主动陪伴" icon={Activity}><PolicyList items={presence as unknown as Item[]} /><Pagination pagination={presenceQuery.data?.pagination} page={presencePage} onPageChange={setPresencePage} disabled={presenceQuery.isFetching} /></Panel></div>}</>;
}

function PolicyList({ items, selectedId, onSelect }: { items: Item[]; selectedId?: string; onSelect?: (id: string) => void }) { return <div className="detail-record-list">{items.map((item, index) => { const content = <><span><strong>{value(item, "selected_action", value(item, "status", "运行记录"))}</strong><small>用于评估伙伴策略，不直接改变当前行为</small></span><em>{value(item, "reward_prediction", value(item, "status"))}</em></>; const id = value(item, "id", String(index)); return onSelect ? <button key={id} type="button" className={`detail-record ${selectedId === id ? "is-selected" : ""}`} onClick={() => onSelect(id)}>{content}</button> : <div key={id} className="detail-record">{content}</div>; })}{!items.length ? <Empty>当前没有策略运行记录。</Empty> : null}</div>; }

export function SystemWorkspace({ view = "overview", focus }: { view?: SystemView; focus?: "reranker" | "presence" }) {
  const content = view === "provider" ? <ProviderView /> : view === "permissions" ? <PermissionView /> : view === "data-privacy" ? <DataPrivacyView /> : view === "diagnostics" ? <DiagnosticsView /> : view === "policy" || view === "reranker" || view === "presence" ? <PolicyView focus={focus ?? (view === "reranker" || view === "presence" ? view : undefined)} /> : <DiagnosticsView />;
  return <Shell view={view}>{content}</Shell>;
}
