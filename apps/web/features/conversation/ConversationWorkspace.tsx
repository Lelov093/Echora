"use client";

import Link from "next/link";
import { FormEvent, KeyboardEvent as ReactKeyboardEvent, memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { ArrowDown, Brain, Check, ChevronDown, ChevronLeft, ChevronRight, Clock3, FileClock, History, ListChecks, LoaderCircle, Menu, PanelLeftClose, Pause, Play, Plus, RotateCcw, Search, Send, Settings2, ShieldCheck, Sparkles, Square, Wrench, X, Zap } from "lucide-react";
import { cancelConversationTurn, conversationTurnEventUrl, createConversation, getConversation, getConversationMessageEvidence, getConversationTurn, getLatestConversationTurn, listConversations, listMessages, retryConversationProvider, startConversationTurn, updateConversation, type ConversationMessageEvidence, type ConversationTurnLifecycleStatus, type ConversationTurnStatus, type MessageBrief, type ReasoningMode, type RunResult } from "@/lib/api/conversations";
import { acceptCandidate, commitCandidate, editCandidate, listMemoryCandidates, rejectCandidate, type MemoryCandidate } from "@/lib/api/memories";
import { commitGrowth, listGrowthCandidates, rejectGrowth, type GrowthCandidate } from "@/lib/api/growth";
import { useCompanionRosterQuery, useCompanionWorkspaceQuery } from "@/lib/queries/companions";
import { DataState } from "@/components/patterns/DataState";
import { ApiError } from "@/lib/api/client";
import { ConversationListItem, MessageLifecycleActions } from "@/features/conversation/ConversationLifecycleControls";
import { ConversationMessageContent } from "@/features/conversation/ConversationMessageContent";
import { cancelToolRun, confirmToolRun, listToolRuns, retryToolRun, type ToolRun } from "@/lib/api/tools";
import { controlConversationTask, listConversationTasks, type ConversationTaskRun } from "@/lib/api/conversationTasks";
import type { PaginatedItems } from "@/lib/types";

type SideTab = "context" | "task" | "review" | "why";
const terminalTurnStatuses: ConversationTurnLifecycleStatus[] = ["completed", "failed", "cancelled"];

function mergeLatestMessagePage(
  current: InfiniteData<PaginatedItems<MessageBrief>, number> | undefined,
  latest: PaginatedItems<MessageBrief>,
): InfiniteData<PaginatedItems<MessageBrief>, number> {
  if (!current) return { pages: [latest], pageParams: [1] };
  const loadedPageCount = Math.min(
    current.pages.length,
    latest.pagination.total_pages,
  );
  const loadedCapacity = loadedPageCount * latest.pagination.page_size;
  const merged = new Map<string, MessageBrief>();
  for (const message of [
    ...latest.items,
    ...current.pages.flatMap((page) => page.items),
  ]) {
    merged.set(message.id, message);
  }
  const newest = [...merged.values()]
    .sort((left, right) => (
      right.created_at.localeCompare(left.created_at) || right.id.localeCompare(left.id)
    ))
    .slice(0, loadedCapacity);
  return {
    pages: Array.from({ length: loadedPageCount }, (_, index) => ({
      items: newest.slice(
        index * latest.pagination.page_size,
        (index + 1) * latest.pagination.page_size,
      ),
      pagination: {
        ...latest.pagination,
        page: index + 1,
      },
    })),
    pageParams: current.pageParams.slice(0, loadedPageCount),
  };
}

const workflowStatusLabels = {
  completed: "已完成",
  in_progress: "进行中",
  attention: "需要留意",
} as const;

function providerDisplayName(value?: string | null) {
  if (!value) return "未记录";
  if (value === "openai_compatible") return "OpenAI 兼容接口";
  if (value === "ark") return "火山引擎 Ark";
  return value.replaceAll("_", " ");
}

function nextStepLabel(run: RunResult) {
  const tool = run.tool_runs?.at(-1);
  if (tool?.status === "awaiting_input") return "工具还需要补充参数，请直接在对话里回答。";
  if (tool?.status === "awaiting_confirmation") return "这次操作会写入状态，等待你的明确确认。";
  if (tool?.status === "retry_scheduled") return "外部服务暂不可用，已进入持久重试队列。";
  if (tool?.status === "succeeded") return "工具已真实执行，结果和证据已返回这段对话。";
  if (run.memory_candidates.length || run.growth_candidates.length) return "本轮形成了待确认内容，可在准备好时查看。";
  if (run.presence_opportunities.length) return "伙伴留下了一条在场感建议，可在准备好时查看。";
  return "准备好时继续这段对话。";
}

function turnStageLabel(companionName: string, turn?: ConversationTurnStatus) {
  const labels: Partial<Record<ConversationTurnLifecycleStatus, string>> = {
    accepted: "消息已保存，正在等待伙伴回应",
    context_preparing: "正在整理这段对话的上下文",
    provider_waiting: "正在等待真实 Provider 回应",
    streaming: "正在接收回应",
    response_persisted: "回应已保存，正在整理后续状态",
    effects_processing: "正在整理记忆与关系候选",
  };
  return turn?.status && labels[turn.status] ? labels[turn.status] : `${companionName} 正在准备回应`;
}

export function ConversationWorkspace({ companionId, conversationId }: { companionId: string; conversationId: string }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [conversationSearch, setConversationSearch] = useState("");
  const [conversationPage, setConversationPage] = useState(1);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<SideTab | null>(null);
  const [lastRun, setLastRun] = useState<RunResult | null>(null);
  const [traceOpen, setTraceOpen] = useState(false);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const [failedTraceId, setFailedTraceId] = useState<string | null>(null);
  const [activeTurnTraceId, setActiveTurnTraceId] = useState<string | null>(null);
  const [selectedEvidenceMessageId, setSelectedEvidenceMessageId] = useState<string | null>(null);
  const [pendingUserMessage, setPendingUserMessage] = useState<MessageBrief | null>(null);
  const [reasoningModeOverride, setReasoningModeOverride] = useState<ReasoningMode | null>(null);
  const [streamConnectedTraceId, setStreamConnectedTraceId] = useState<string | null>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const messagesViewportRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialScrollDoneRef = useRef(false);
  const stayAtBottomRef = useRef(true);
  const workspace = useCompanionWorkspaceQuery(companionId);
  const roster = useCompanionRosterQuery();
  const currentCompanion = roster.data?.items.find((item) => item.id === companionId);
  const conversations = useQuery({ queryKey: ["conversations", companionId, conversationPage], queryFn: () => listConversations({ companion_id: companionId, page: conversationPage, page_size: 8 }) });
  const currentConversationQuery = useQuery({ queryKey: ["conversation", conversationId, companionId], queryFn: () => getConversation(conversationId, companionId) });
  const messages = useInfiniteQuery({
    queryKey: ["messages", conversationId],
    queryFn: ({ pageParam }) => listMessages(conversationId, companionId, pageParam, 50, "desc"),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (
      lastPage.pagination.page < lastPage.pagination.total_pages
        ? lastPage.pagination.page + 1
        : undefined
    ),
  });
  const toolRuns = useQuery({ queryKey: ["tool-runs", companionId, conversationId], queryFn: () => listToolRuns({ companion_id: companionId, conversation_id: conversationId, page_size: 20 }), staleTime: 5_000 });
  const taskRuns = useQuery({
    queryKey: ["conversation-tasks", companionId, conversationId],
    queryFn: () => listConversationTasks(companionId, conversationId),
    staleTime: 3_000,
    refetchInterval: (query) => (
      (query.state.data as ConversationTaskRun[] | undefined)?.some((task) =>
        ["ready", "running", "awaiting_approval"].includes(task.status),
      ) ? 2_000 : false
    ),
  });
  const memoryCandidates = useQuery({ queryKey: ["memory-candidates", companionId], queryFn: () => listMemoryCandidates({ companion_id: companionId, status: "pending", page_size: "50" }) });
  const growthCandidates = useQuery({ queryKey: ["growth-candidates", companionId], queryFn: () => listGrowthCandidates({ companion_id: companionId, status: "candidate", page_size: "50" }) });
  const latestTurn = useQuery({
    queryKey: ["conversation-turn-current", conversationId, companionId],
    queryFn: () => getLatestConversationTurn(conversationId, companionId),
    enabled: !activeTurnTraceId,
    refetchInterval: (query) => {
      const turn = query.state.data as ConversationTurnStatus | null | undefined;
      if (!turn?.status || terminalTurnStatuses.includes(turn.status)) return false;
      return streamConnectedTraceId === turn.trace_run_id ? false : 1_500;
    },
  });
  const activeTurn = useQuery({
    queryKey: ["conversation-turn", conversationId, activeTurnTraceId, companionId],
    queryFn: () => getConversationTurn(conversationId, activeTurnTraceId!, companionId),
    enabled: Boolean(activeTurnTraceId),
    refetchInterval: (query) => {
      const turn = query.state.data as ConversationTurnStatus | undefined;
      if (!turn?.status || terminalTurnStatuses.includes(turn.status)) return false;
      return streamConnectedTraceId === turn.trace_run_id ? false : 1_500;
    },
  });
  const effectiveTurn = activeTurn.data ?? latestTurn.data ?? undefined;
  const effectiveTurnStatus = effectiveTurn?.status;
  const effectiveTurnTraceId = effectiveTurn?.trace_run_id;
  const displayRun = effectiveTurn?.status === "completed" && effectiveTurn.result ? effectiveTurn.result : lastRun;
  const displayFailedTraceId = effectiveTurn?.status === "failed" ? effectiveTurn.trace_run_id : failedTraceId;
  const currentConversation = currentConversationQuery.data ?? conversations.data?.items.find((item) => item.id === conversationId);
  const reasoningMode = reasoningModeOverride ?? currentConversation?.reasoning_mode ?? "auto";
  const refetchToolRuns = toolRuns.refetch;
  const refetchTaskRuns = taskRuns.refetch;
  const persistedMessages = useMemo(
    () => (messages.data?.pages.flatMap((page) => page.items) ?? []).reverse(),
    [messages.data?.pages],
  );
  const messageItems = useMemo(() => {
    const persisted = persistedMessages;
    if (!pendingUserMessage || persisted.some((message) => message.id === pendingUserMessage.id || (message.role === "user" && message.content === pendingUserMessage.content && message.created_at >= pendingUserMessage.created_at))) return persisted;
    return [...persisted, pendingUserMessage];
  }, [pendingUserMessage, persistedMessages]);
  const representedToolResultMessageIds = useMemo(
    () => new Set(
      (toolRuns.data?.items ?? [])
        .map((toolRun) => toolRun.result_message_id)
        .filter((messageId): messageId is string => Boolean(messageId)),
    ),
    [toolRuns.data?.items],
  );
  const selectedEvidenceIsCurrent = Boolean(selectedEvidenceMessageId && messageItems.some((message) => message.id === selectedEvidenceMessageId && message.role === "assistant"));
  const evidenceMessageId = selectedEvidenceIsCurrent ? selectedEvidenceMessageId : null;
  const evidence = useQuery({
    queryKey: ["conversation-message-evidence", conversationId, evidenceMessageId, companionId],
    queryFn: () => getConversationMessageEvidence(conversationId, evidenceMessageId!, companionId),
    enabled: Boolean(evidenceMessageId && (drawerTab === "context" || drawerTab === "task" || drawerTab === "why" || traceOpen)),
  });
  const selectedTask = useMemo(
    () => evidence.data?.activity.task_run_id
      ? (taskRuns.data ?? []).find((task) => task.id === evidence.data?.activity.task_run_id) ?? null
      : null,
    [evidence.data?.activity.task_run_id, taskRuns.data],
  );
  const currentMemoryCandidates = useMemo(() => (memoryCandidates.data?.items ?? []).filter((candidate) => candidate.source_conversation_id === conversationId), [conversationId, memoryCandidates.data?.items]);
  const currentGrowthCandidates = useMemo(() => (growthCandidates.data?.items ?? []).filter((candidate) => candidate.conversation_id === conversationId), [conversationId, growthCandidates.data?.items]);
  const reviewCount = currentMemoryCandidates.length + currentGrowthCandidates.length;
  const companionReviewCount = workspace.data?.review_counts.total ?? (memoryCandidates.data?.items.length ?? 0) + (growthCandidates.data?.items.length ?? 0);
  const conversationArchived = currentConversation?.status === "archived";
  const filteredConversations = useMemo(() => {
    const needle = conversationSearch.trim().toLocaleLowerCase("zh-CN");
    if (!needle) return conversations.data?.items ?? [];
    return (conversations.data?.items ?? []).filter((item) => `${item.title} ${item.current_topic ?? ""} ${item.current_goal ?? ""}`.toLocaleLowerCase("zh-CN").includes(needle));
  }, [conversationSearch, conversations.data?.items]);

  const refreshConversationCrud = useCallback(() => Promise.all([
    queryClient.invalidateQueries({ queryKey: ["messages", conversationId] }),
    queryClient.invalidateQueries({ queryKey: ["conversations", companionId] }),
  ]), [companionId, conversationId, queryClient]);
  const handleConversationDeleted = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["conversations", companionId] });
    window.location.assign(`/companions/${companionId}`);
  }, [companionId, queryClient]);
  const refreshLatestMessages = useCallback(async () => {
    const latest = await listMessages(conversationId, companionId, 1, 50, "desc");
    queryClient.setQueryData<InfiniteData<PaginatedItems<MessageBrief>, number>>(
      ["messages", conversationId],
      (current) => mergeLatestMessagePage(current, latest),
    );
  }, [companionId, conversationId, queryClient]);
  const create = useMutation({
    mutationFn: (retentionMode: "standard" | "temporary") => createConversation({ user_id: currentCompanion?.user_id, companion_id: companionId, title: retentionMode === "temporary" ? "临时对话" : "新的对话", mode_key: workspace.data?.companion.current_mode ?? "project", retention_mode: retentionMode }),
    onSuccess: (conversation) => window.location.assign(`/companions/${companionId}/conversations/${conversation.id}`),
  });
  const updateRetention = useMutation({
    mutationFn: (enabled: boolean) => updateConversation(conversationId, companionId, { cross_session_memory_enabled: enabled }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["conversation", conversationId, companionId] }); },
  });
  const updateReasoningMode = useMutation({
    mutationFn: (mode: ReasoningMode) => updateConversation(conversationId, companionId, { reasoning_mode: mode }),
    onSuccess: async (conversation) => {
      queryClient.setQueryData(["conversation", conversationId, companionId], conversation);
      setReasoningModeOverride(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["conversations", companionId] }),
      ]);
    },
    onError: () => setReasoningModeOverride(null),
  });
  const run = useMutation({
    mutationFn: ({ content, idempotencyKey, continuationOfTraceRunId }: { content: string; idempotencyKey: string; continuationOfTraceRunId?: string }) => startConversationTurn(conversationId, { companion_id: companionId, content, idempotency_key: idempotencyKey, continuation_of_trace_run_id: continuationOfTraceRunId, mode_key: workspace.data?.companion.current_mode, reasoning_mode: reasoningMode }),
    onSuccess: async (turn) => {
      setActiveTurnTraceId(turn.trace_run_id);
      queryClient.setQueryData(["conversation-turn", conversationId, turn.trace_run_id, companionId], turn);
      queryClient.setQueryData(["conversation-turn-current", conversationId, companionId], turn);
      setFailedTraceId(null);
      await refreshLatestMessages();
      setPendingUserMessage(null);
      composerRef.current?.focus();
    },
    onError: (error, variables) => {
      if (error instanceof ApiError && typeof error.details?.trace_run_id === "string") setFailedTraceId(error.details.trace_run_id);
      setDraft((current) => current || variables.content);
      setPendingUserMessage(null);
      void refreshLatestMessages();
    },
  });

  const cancelTurn = useMutation({
    mutationFn: (traceRunId: string) => cancelConversationTurn(conversationId, traceRunId, companionId),
    onSuccess: async (turn) => {
      queryClient.setQueryData(["conversation-turn", conversationId, turn.trace_run_id, companionId], turn);
      queryClient.setQueryData(["conversation-turn-current", conversationId, companionId], turn);
      await queryClient.invalidateQueries({ queryKey: ["conversation-turn", conversationId] });
    },
  });
  const retryProvider = useMutation({
    mutationFn: (traceRunId: string) => retryConversationProvider(conversationId, traceRunId, companionId),
    onSuccess: async (result) => {
      setLastRun(result);
      setActiveTurnTraceId(null);
      setFailedTraceId(null);
      setDraft("");
      run.reset();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["messages", conversationId] }),
        queryClient.invalidateQueries({ queryKey: ["conversations", companionId] }),
        queryClient.invalidateQueries({ queryKey: ["memory-candidates", companionId] }),
        queryClient.invalidateQueries({ queryKey: ["growth-candidates", companionId] }),
        queryClient.invalidateQueries({ queryKey: ["conversation-message-evidence", conversationId] }),
      ]);
      composerRef.current?.focus();
    },
    onError: (error) => {
      if (error instanceof ApiError && typeof error.details?.trace_run_id === "string") setFailedTraceId(error.details.trace_run_id);
    },
  });
  const toolAction = useMutation({
    mutationFn: ({ run, action }: { run: ToolRun; action: "confirm" | "cancel" | "retry" }) => {
      const scope = { companion_id: companionId, conversation_id: conversationId };
      return action === "confirm" ? confirmToolRun(run.id, scope) : action === "cancel" ? cancelToolRun(run.id, scope) : retryToolRun(run.id, scope);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["messages", conversationId] }),
        queryClient.invalidateQueries({ queryKey: ["tool-runs", companionId, conversationId] }),
        queryClient.invalidateQueries({ queryKey: ["conversation-message-evidence", conversationId, evidenceMessageId, companionId] }),
      ]);
    },
  });
  const taskAction = useMutation({
    mutationFn: ({ task, action }: { task: ConversationTaskRun; action: "pause" | "resume" | "cancel" }) =>
      controlConversationTask(task.id, action, companionId, conversationId),
    onSuccess: async (task) => {
      queryClient.setQueryData<ConversationTaskRun[]>(
        ["conversation-tasks", companionId, conversationId],
        (current) => current?.map((item) => item.id === task.id ? task : item) ?? [task],
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["conversation-tasks", companionId, conversationId] }),
        queryClient.invalidateQueries({ queryKey: ["tool-runs", companionId, conversationId] }),
        queryClient.invalidateQueries({ queryKey: ["conversation-message-evidence", conversationId, evidenceMessageId, companionId] }),
      ]);
    },
  });

  useEffect(() => {
    if (!effectiveTurnStatus || !terminalTurnStatuses.includes(effectiveTurnStatus)) return;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["conversations", companionId] }),
      queryClient.invalidateQueries({ queryKey: ["memory-candidates", companionId] }),
      queryClient.invalidateQueries({ queryKey: ["growth-candidates", companionId] }),
      queryClient.invalidateQueries({ queryKey: ["conversation-message-evidence", conversationId] }),
      queryClient.invalidateQueries({ queryKey: ["tool-runs", companionId, conversationId] }),
      queryClient.invalidateQueries({ queryKey: ["conversation-tasks", companionId, conversationId] }),
    ]);
    composerRef.current?.focus();
  }, [effectiveTurnStatus, effectiveTurnTraceId, companionId, conversationId, queryClient]);

  useEffect(() => {
    if (drawerTab !== "task") return;
    void Promise.all([
      refetchToolRuns(),
      refetchTaskRuns(),
      queryClient.refetchQueries({ queryKey: ["conversation-message-evidence", conversationId, evidenceMessageId, companionId] }),
    ]);
  }, [companionId, conversationId, drawerTab, evidenceMessageId, queryClient, refetchToolRuns, refetchTaskRuns]);

  useEffect(() => {
    if (!effectiveTurnStatus || terminalTurnStatuses.includes(effectiveTurnStatus)) return;
    const refreshActivity = () => {
      void Promise.all([
        queryClient.refetchQueries({ queryKey: ["tool-runs", companionId, conversationId] }),
        queryClient.refetchQueries({ queryKey: ["conversation-tasks", companionId, conversationId] }),
        queryClient.refetchQueries({ queryKey: ["conversation-message-evidence", conversationId, evidenceMessageId, companionId] }),
      ]);
    };
    refreshActivity();
    const interval = window.setInterval(refreshActivity, 2_000);
    return () => window.clearInterval(interval);
  }, [effectiveTurnStatus, effectiveTurnTraceId, companionId, conversationId, evidenceMessageId, queryClient]);

  const resizeComposer = useCallback(() => {
    const textarea = composerRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const maxHeight = Math.min(window.innerHeight * 0.4, 240);
    const nextHeight = Math.max(31, Math.min(textarea.scrollHeight, maxHeight));
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
    textarea.form?.style.setProperty("--conversation-input-height", `${nextHeight}px`);
  }, []);

  useLayoutEffect(() => {
    resizeComposer();
  }, [draft, resizeComposer]);

  useEffect(() => {
    window.addEventListener("resize", resizeComposer);
    return () => window.removeEventListener("resize", resizeComposer);
  }, [resizeComposer]);

  useEffect(() => {
    const viewport = messagesViewportRef.current;
    if (!viewport || !messages.isSuccess) return;
    const frame = window.requestAnimationFrame(() => {
      if (!initialScrollDoneRef.current || stayAtBottomRef.current) viewport.scrollTop = viewport.scrollHeight;
      initialScrollDoneRef.current = true;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [persistedMessages.length, messages.isSuccess, run.isPending, activeTurnTraceId, retryProvider.isPending]);

  useEffect(() => {
    const viewport = messagesViewportRef.current;
    if (!viewport || !messageItems.length) return;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActiveMessageId((visible.target as HTMLElement).dataset.messageId ?? null);
    }, { root: viewport, rootMargin: "-28% 0px -52% 0px", threshold: [0, 0.4, 0.8] });
    viewport.querySelectorAll<HTMLElement>("[data-message-id]").forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [messageItems.length]);

  useEffect(() => {
    const close = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setTraceOpen(false);
      setDrawerTab(null);
      setMobileSidebarOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);

  const handleStreamConnection = useCallback((traceRunId: string, connected: boolean) => {
    setStreamConnectedTraceId((current) => {
      if (connected) return traceRunId;
      return current === traceRunId ? null : current;
    });
    if (connected) setActiveTurnTraceId((current) => current ?? traceRunId);
  }, []);

  const handleStreamStatus = useCallback((
    traceRunId: string,
    status: ConversationTurnLifecycleStatus,
  ) => {
    const mergeStatus = (current: ConversationTurnStatus | null | undefined) => (
      current?.trace_run_id === traceRunId ? { ...current, status } : current
    );
    queryClient.setQueryData(
      ["conversation-turn", conversationId, traceRunId, companionId],
      mergeStatus,
    );
    queryClient.setQueryData(
      ["conversation-turn-current", conversationId, companionId],
      mergeStatus,
    );
    if (terminalTurnStatuses.includes(status)) {
      setStreamConnectedTraceId((current) => current === traceRunId ? null : current);
      void queryClient.invalidateQueries({
        queryKey: ["conversation-turn", conversationId, traceRunId, companionId],
        exact: true,
      });
    }
  }, [companionId, conversationId, queryClient]);

  const openMessagePanel = useCallback((messageId: string, tab: Exclude<SideTab, "review">) => {
    setSelectedEvidenceMessageId(messageId);
    setDrawerTab(tab);
    setMobileSidebarOpen(false);
  }, []);

  function handleMessagesScroll() {
    const viewport = messagesViewportRef.current;
    if (!viewport) return;
    const distance = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    stayAtBottomRef.current = distance < 120;
    setShowJumpToLatest(distance >= 160);
  }

  function jumpToLatest() {
    stayAtBottomRef.current = true;
    messagesEndRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }

  async function loadOlderMessages() {
    const viewport = messagesViewportRef.current;
    if (!viewport || !messages.hasNextPage || messages.isFetchingNextPage) return;
    const previousHeight = viewport.scrollHeight;
    await messages.fetchNextPage();
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        viewport.scrollTop += viewport.scrollHeight - previousHeight;
      });
    });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || responding || conversationArchived) return;
    run.reset();
    retryProvider.reset();
    setFailedTraceId(null);
    stayAtBottomRef.current = true;
    startTurn(content);
  }

  function startTurn(content: string, continuationOfTraceRunId?: string) {
    const idempotencyKey = crypto.randomUUID();
    setPendingUserMessage({ id: `pending-${idempotencyKey}`, role: "user", content, content_format: "text", created_at: new Date().toISOString() });
    setDraft("");
    run.mutate({ content, idempotencyKey, continuationOfTraceRunId });
  }

  function handleComposerKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function openDrawer(tab: SideTab) {
    if (tab === "review") setSelectedEvidenceMessageId(null);
    setDrawerTab(tab);
    setMobileSidebarOpen(false);
  }

  if (workspace.isLoading || messages.isLoading) return <DataState kind="loading" title="正在恢复长期对话" description="正在读取这段关系的真实消息与上下文。" />;
  if (workspace.isError || messages.isError || !workspace.data) return <DataState kind="error" title="暂时无法打开对话" description="你的消息没有丢失，请确认 API 状态后重试。" />;

  const runError = retryProvider.error instanceof ApiError ? retryProvider.error : run.error instanceof ApiError ? run.error : null;
  const generationActive = Boolean(effectiveTurn && ["accepted", "context_preparing", "provider_waiting", "streaming", "cancellation_requested"].includes(effectiveTurn.status));
  const turnStillOpen = Boolean(effectiveTurn && !terminalTurnStatuses.includes(effectiveTurn.status));
  const responding = run.isPending || generationActive || retryProvider.isPending;
  const cancellableTraceId = generationActive ? (activeTurnTraceId ?? effectiveTurn?.trace_run_id ?? null) : null;
  const streamTraceId = turnStillOpen ? (activeTurnTraceId ?? effectiveTurn?.trace_run_id ?? null) : null;
  const companionName = workspace.data.companion.name;
  return (
    <section className={`refoundation-conversation conversation-workspace${sidebarCollapsed ? " is-sidebar-collapsed" : ""}${mobileSidebarOpen ? " is-mobile-sidebar-open" : ""}`}>
      <aside className="conversation-sidebar" aria-label="伙伴与会话">
        <div className="conversation-sidebar-brand">
          <Link href="/" aria-label="返回产品首页"><span aria-hidden="true" /><strong>Echora</strong></Link>
          <button type="button" onClick={() => setSidebarCollapsed(true)} aria-label="收起会话侧栏"><PanelLeftClose size={18} /></button>
        </div>
        <Link className="conversation-companion-entry" href={`/companions/${companionId}`}>
          <span className="conversation-companion-orb" aria-hidden="true" />
          <span><strong>{companionName}</strong><small>{workspace.data.identity.relationship_role || "我的伙伴"}</small></span>
          <ChevronLeft size={16} aria-hidden="true" />
        </Link>
        <div className="conversation-sidebar-heading">
          <span>会话</span>
          <span className="conversation-create-actions"><button type="button" onClick={() => create.mutate("temporary")} disabled={create.isPending} aria-label="新建临时对话"><Clock3 size={16} /></button><button type="button" onClick={() => create.mutate("standard")} disabled={create.isPending} aria-label="新建标准对话"><Plus size={18} /></button></span>
        </div>
        <label className="conversation-search"><Search size={16} aria-hidden="true" /><input value={conversationSearch} onChange={(event) => setConversationSearch(event.target.value)} placeholder="搜索会话" aria-label="搜索会话" /></label>
        <nav className="conversation-list" aria-label="长期会话列表">
          {filteredConversations.map((conversation) => {
            const isCurrent = conversation.id === conversationId;
            return <ConversationListItem key={conversation.id} conversation={conversation} companionId={companionId} current={isCurrent} onChanged={refreshConversationCrud} onDeleted={isCurrent ? handleConversationDeleted : refreshConversationCrud} onNavigate={() => setMobileSidebarOpen(false)} />;
          })}
          {!filteredConversations.length ? <p className="conversation-list-empty">没有匹配的会话</p> : null}
        </nav>
        {(conversations.data?.pagination?.total_pages ?? 1) > 1 ? <nav className="conversation-list-pagination" aria-label="会话列表分页"><button type="button" disabled={conversationPage <= 1} onClick={() => setConversationPage((page) => Math.max(1, page - 1))} aria-label="上一页会话"><ChevronLeft size={16} /></button><span>{conversationPage} / {conversations.data?.pagination?.total_pages}</span><button type="button" disabled={conversationPage >= (conversations.data?.pagination?.total_pages ?? 1)} onClick={() => setConversationPage((page) => page + 1)} aria-label="下一页会话"><ChevronRight size={16} /></button></nav> : null}
        <nav className="conversation-sidebar-tools" aria-label="伙伴功能">
          <button type="button" onClick={() => openDrawer("review")}><ShieldCheck size={17} />本对话待确认{reviewCount ? <b>{reviewCount}</b> : null}</button>
          <Link href={`/settings/companions/${companionId}/profile?return_to=${encodeURIComponent(`/companions/${companionId}/conversations/${conversationId}`)}`}><Settings2 size={17} />伙伴设置</Link>
        </nav>
      </aside>
      <button className="conversation-sidebar-backdrop" type="button" onClick={() => setMobileSidebarOpen(false)} aria-label="关闭会话侧栏" />

      <main className="conversation-thread">
        <div className="conversation-floating-toolbar">
          <button type="button" className="conversation-open-sidebar" onClick={() => { setSidebarCollapsed(false); setMobileSidebarOpen(true); }} aria-label="打开会话侧栏"><Menu size={19} /></button>
          <button type="button" className="conversation-title-button" onClick={() => setMobileSidebarOpen(true)}><strong>{currentConversation?.title || "未命名对话"}</strong><small>{companionName}</small></button>
        </div>


        {currentConversation?.retention_mode === "temporary" ? <div className="conversation-retention-banner"><Clock3 size={16} /><span>临时对话：不读取或写入长期记忆，不显示在历史列表；必要安全 Trace 保留至 {currentConversation.retention_expires_at ? new Date(currentConversation.retention_expires_at).toLocaleDateString("zh-CN") : "到期日"}。</span></div> : currentConversation ? <label className="conversation-memory-toggle"><input type="checkbox" checked={currentConversation.cross_session_memory_enabled} disabled={updateRetention.isPending} onChange={(event) => updateRetention.mutate(event.target.checked)} /><span>跨会话记忆</span></label> : null}

        <div className="conversation-messages" ref={messagesViewportRef} onScroll={handleMessagesScroll} aria-live="polite">
          <div className="conversation-message-column">
            {!messageItems.length ? <div className="conversation-empty"><span className="conversation-companion-orb" aria-hidden="true" /><h1>从你真正关心的事开始</h1><p>{companionName} 会在自己的身份、记忆和关系边界内回应。</p></div> : null}
            {messages.hasNextPage ? <button type="button" className="conversation-load-older" onClick={loadOlderMessages} disabled={messages.isFetchingNextPage}>{messages.isFetchingNextPage ? "正在读取更早消息…" : "加载更早消息"}</button> : null}
            {messageItems.map((message) => {
              if (message.role === "tool" && representedToolResultMessageIds.has(message.id)) return null;
              return <ConversationMessage key={message.id} message={message} companionName={companionName} conversationId={conversationId} companionId={companionId} onChanged={refreshConversationCrud} onOpenPanel={message.role === "assistant" && !message.id.startsWith("pending-") ? openMessagePanel : undefined} />;
            })}
            {streamTraceId ? <StreamingTurnMessage key={streamTraceId} conversationId={conversationId} companionId={companionId} traceRunId={streamTraceId} companionName={companionName} onConnectionChange={handleStreamConnection} onStatus={handleStreamStatus} onResponsePersisted={refreshLatestMessages} /> : null}
            {responding && effectiveTurn?.status !== "streaming" ? <div className="conversation-running"><span className="conversation-companion-orb" aria-hidden="true" /><LoaderCircle size={18} className="animate-spin" /><span>{retryProvider.isPending ? "正在重试真实 Provider，不会重复保存你的消息" : turnStageLabel(companionName, effectiveTurn)}</span></div> : null}
            {(run.isError || retryProvider.isError || displayFailedTraceId) && !responding ? <div className="conversation-run-error" role="alert"><strong>真实模型暂时无法回应</strong><span>{runError?.message || "本次没有生成或保存模拟回复，你的输入已保留。请检查 Provider 后重试。"}</span>{runError?.details?.provider_error_code ? <small>Provider：{String(runError.details.provider_error_code)}</small> : null}{displayFailedTraceId ? <button type="button" onClick={() => retryProvider.mutate(displayFailedTraceId)} disabled={retryProvider.isPending}>重试本次回应</button> : null}</div> : null}
            {effectiveTurn?.status === "cancelled" && !responding ? <button type="button" className="conversation-turn-notice" onClick={() => startTurn("请从刚才停止的位置继续回应。", effectiveTurn.trace_run_id)}><RotateCcw size={15} /><span>继续回应（将开始新一轮）</span></button> : null}
            {displayRun ? <button type="button" className="conversation-turn-notice" onClick={() => { if (displayRun.memory_candidates.length || displayRun.growth_candidates.length) openDrawer("review"); else { setSelectedEvidenceMessageId(displayRun.assistant_message.id); openDrawer("why"); } }}><Sparkles size={15} /><span>{nextStepLabel(displayRun)}</span></button> : null}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {messageItems.length > 5 ? <nav className="conversation-quick-index" aria-label="消息快速索引">{messageItems.map((message, index) => <button key={message.id} type="button" className={activeMessageId === message.id ? "is-active" : undefined} onClick={() => document.getElementById(`conversation-message-${message.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })} aria-label={`跳转到第 ${index + 1} 条${message.role === "user" ? "你的消息" : `${companionName} 的回复`}`} title={`第 ${index + 1} 条消息`}><span /></button>)}</nav> : null}
        {showJumpToLatest ? <button type="button" className="conversation-jump-latest" onClick={jumpToLatest}><ArrowDown size={17} /><span>回到最新消息</span></button> : null}

        <form className="conversation-composer" onSubmit={submit}>
          <textarea ref={composerRef} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder={`告诉 ${companionName} 你此刻在想什么…`} aria-label="输入消息" rows={1} disabled={conversationArchived} />
          <div className="conversation-composer-meta">
            <ReasoningModeSelector
              mode={reasoningMode}
              onChange={(mode) => {
                setReasoningModeOverride(mode);
                updateReasoningMode.mutate(mode);
              }}
              disabled={conversationArchived || updateReasoningMode.isPending}
              saving={updateReasoningMode.isPending}
              error={updateReasoningMode.isError}
            />
            <span className="conversation-composer-hint">{conversationArchived ? "这段对话已归档，请从左侧菜单恢复后继续" : responding ? "模式调整会用于下一条消息" : "Enter 发送 · Shift + Enter 换行"}</span>
          </div>
          {responding && cancellableTraceId ? <button type="button" className="is-stop" onClick={() => cancelTurn.mutate(cancellableTraceId)} disabled={cancelTurn.isPending || effectiveTurn?.status === "cancellation_requested"} aria-label="停止生成"><Square size={16} fill="currentColor" /></button> : <button type="submit" disabled={!draft.trim() || responding || conversationArchived} aria-label="发送消息"><Send size={18} /></button>}
        </form>
      </main>

      {drawerTab ? <div className="conversation-drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setDrawerTab(null); }}>
        <aside className="conversation-context-drawer" role="dialog" aria-modal="true" aria-label={drawerTab === "review" ? "本对话待确认" : "所选伙伴回复的辅助信息"}>
          <header>
            <div><small>{drawerTab === "review" ? "当前对话" : "所选伙伴回复"}</small><h2>{drawerTab === "context" ? "本轮上下文" : drawerTab === "task" ? "本轮活动" : drawerTab === "review" ? "本对话待确认" : "回复依据"}</h2></div>
            <button type="button" onClick={() => setDrawerTab(null)} aria-label="关闭辅助信息"><X size={19} /></button>
          </header>
          {drawerTab !== "review" ? <div className="conversation-drawer-tabs" role="tablist" aria-label="所选回复的辅助信息">
            <button role="tab" aria-selected={drawerTab === "context"} onClick={() => setDrawerTab("context")}><span>本轮上下文<small>回复前采用</small></span></button>
            <button role="tab" aria-selected={drawerTab === "task"} onClick={() => setDrawerTab("task")}><span>本轮活动<small>任务与工具</small></span></button>
            <button role="tab" aria-selected={drawerTab === "why"} onClick={() => setDrawerTab("why")}><span>回复依据<small>事实与结果</small></span></button>
          </div> : null}
          {drawerTab === "context" ? <ContextPanel evidence={evidence.data} loading={evidence.isLoading} error={evidence.isError} selected={selectedEvidenceIsCurrent} /> : null}
          {drawerTab === "task" ? <TaskActivityPanel task={selectedTask} toolRuns={evidence.data?.tools.runs ?? []} loading={evidence.isLoading} error={evidence.isError} selected={selectedEvidenceIsCurrent} taskBusy={taskAction.isPending} taskError={taskAction.error} toolBusy={toolAction.isPending} toolError={toolAction.error} onTaskAction={(task, action) => taskAction.mutate({ task, action })} onToolAction={(toolRun, action) => toolAction.mutate({ run: toolRun, action })} /> : null}
          {drawerTab === "review" ? <ReviewPanel companionId={companionId} conversationId={conversationId} memories={currentMemoryCandidates} growth={currentGrowthCandidates} companionReviewCount={companionReviewCount} reviewCounts={workspace.data.review_counts} /> : null}
          {drawerTab === "why" ? <WhyPanel evidence={evidence.data} loading={evidence.isLoading} error={evidence.isError} selected={selectedEvidenceIsCurrent} onTrace={() => setTraceOpen(true)} /> : null}
        </aside>
      </div> : null}

      {traceOpen ? <div className="trace-drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setTraceOpen(false); }}><aside className="conversation-trace-drawer" role="dialog" aria-modal="true" aria-label="这次回应的过程"><header><div><small>回复依据</small><h2>这次回应的过程</h2></div><button onClick={() => setTraceOpen(false)} aria-label="关闭这次回应的过程"><X size={19} aria-hidden="true" /></button></header><p className="trace-workflow-note">这里按真实运行记录概括伙伴如何完成这次回应。它展示采用的信息、行动和结果，不展示或推测模型的原始思维链。</p>{evidence.isLoading ? <DataState kind="loading" title="正在读取回应过程" /> : evidence.data?.workflow ? <><ol>{evidence.data.workflow.stages.map((stage) => <li key={stage.key}><i className={`is-${stage.status}`} aria-hidden="true" /><div><span><strong>{stage.title}</strong><em>{workflowStatusLabels[stage.status]}</em></span><p>{stage.summary}</p></div></li>)}</ol><details className="trace-provider"><summary>技术运行信息</summary><p>模型服务：{providerDisplayName(evidence.data.response.provider_name)}{evidence.data.response.model_name ? ` · ${evidence.data.response.model_name}` : ""}</p>{evidence.data.response.provider_timing.total_ms ? <p>总耗时：{evidence.data.response.provider_timing.total_ms} ms{evidence.data.response.provider_timing.time_to_first_token_ms != null ? ` · 开始回应 ${evidence.data.response.provider_timing.time_to_first_token_ms} ms` : ""}</p> : null}<p>过程投影：{evidence.data.workflow.version}</p></details></> : <DataState kind="empty" title="本轮还没有可恢复的回应过程" description="旧回复可能没有绑定完整运行记录；系统不会据此补造过程。" />}</aside></div> : null}
    </section>
  );
}

const reasoningModeOptions: Array<{
  value: ReasoningMode;
  label: string;
  description: string;
  icon: typeof Sparkles;
}> = [
  { value: "auto", label: "自动", description: "根据本轮内容与边界自动选择", icon: Sparkles },
  { value: "fast", label: "快速", description: "优先更快开始回答", icon: Zap },
  { value: "thinking", label: "思考", description: "适合规划、解释与复盘", icon: Brain },
  { value: "deep_thinking", label: "深度思考", description: "适合复杂推演与审慎决策", icon: Brain },
];

function ReasoningModeSelector({
  mode,
  onChange,
  disabled,
  saving,
  error,
}: {
  mode: ReasoningMode;
  onChange: (mode: ReasoningMode) => void;
  disabled: boolean;
  saving: boolean;
  error: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = reasoningModeOptions.find((option) => option.value === mode) ?? reasoningModeOptions[0];
  const SelectedIcon = selected.icon;

  useEffect(() => {
    if (!open) return;
    const selectedItem = rootRef.current?.querySelector<HTMLButtonElement>(
      '[role="menuitemradio"][aria-checked="true"]',
    );
    selectedItem?.focus();
    const closeOnOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("pointerdown", closeOnOutside);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("pointerdown", closeOnOutside);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className="conversation-reasoning-selector" ref={rootRef}>
      <button
        type="button"
        className="conversation-reasoning-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
      >
        <SelectedIcon size={14} />
        <span>{saving ? "保存中" : selected.label}</span>
        <ChevronDown size={14} />
      </button>
      {open ? (
        <div
          className="conversation-reasoning-menu"
          role="menu"
          aria-label="回答思考模式"
          onKeyDown={(event) => {
            const items = Array.from(
              event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]'),
            );
            const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
            let nextIndex = currentIndex;
            if (event.key === "ArrowDown") nextIndex = (currentIndex + 1) % items.length;
            else if (event.key === "ArrowUp") nextIndex = (currentIndex - 1 + items.length) % items.length;
            else if (event.key === "Home") nextIndex = 0;
            else if (event.key === "End") nextIndex = items.length - 1;
            else return;
            event.preventDefault();
            items[nextIndex]?.focus();
          }}
        >
          {reasoningModeOptions.map((option) => {
            const Icon = option.icon;
            return (
              <button
                key={option.value}
                type="button"
                role="menuitemradio"
                aria-checked={mode === option.value}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
              >
                <Icon size={16} />
                <span><strong>{option.label}</strong><small>{option.description}</small></span>
                {mode === option.value ? <Check size={16} /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
      <span className="conversation-reasoning-save-state" role="status" aria-live="polite">
        {error ? "模式保存失败，已恢复" : ""}
      </span>
    </div>
  );
}

const ConversationMessage = memo(function ConversationMessage({ message, companionName, conversationId, companionId, onChanged, onOpenPanel }: { message: MessageBrief; companionName: string; conversationId: string; companionId: string; onChanged: () => Promise<unknown>; onOpenPanel?: (messageId: string, tab: Exclude<SideTab, "review">) => void }) {
  if (message.role === "tool") return <ToolResultMessage message={message} />;
  const isHistoricalSimulation = message.role === "assistant" && message.model_provider?.startsWith("mock");
  const useMarkdown = message.role === "assistant" || message.content_format === "markdown";
  const isOptimistic = message.id.startsWith("pending-");
  return <article id={`conversation-message-${message.id}`} data-message-id={message.id} className={`conversation-message is-${message.role}${isHistoricalSimulation ? " is-simulation" : ""}${isOptimistic ? " is-optimistic" : ""}`}><div className="conversation-message-body"><small>{message.role === "user" ? "你" : companionName}{isHistoricalSimulation ? " · 历史模拟回复" : ""}{message.generation_status === "interrupted" ? " · 已停止" : ""}</small><ConversationMessageContent content={message.content} markdown={useMarkdown} /><time>{isOptimistic ? "正在保存…" : message.created_at ? new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(message.created_at)) : ""}</time></div>{message.role === "user" && !isOptimistic ? <MessageLifecycleActions message={message} conversationId={conversationId} companionId={companionId} onChanged={onChanged} /> : onOpenPanel ? <div className="message-lifecycle-actions"><div className="message-action-buttons" aria-label="这条回复的辅助信息"><button type="button" aria-label="查看这条回复的本轮上下文" onClick={() => onOpenPanel(message.id, "context")}><History size={15} aria-hidden="true" /><span>本轮上下文</span></button><button type="button" aria-label="查看这条回复的本轮活动" onClick={() => onOpenPanel(message.id, "task")}><ListChecks size={15} aria-hidden="true" /><span>本轮活动</span></button><button type="button" aria-label="查看这条回复的回复依据" onClick={() => onOpenPanel(message.id, "why")}><FileClock size={15} aria-hidden="true" /><span>回复依据</span></button></div></div> : null}</article>;
});

function StreamingTurnMessage({
  conversationId,
  companionId,
  traceRunId,
  companionName,
  onConnectionChange,
  onStatus,
  onResponsePersisted,
}: {
  conversationId: string;
  companionId: string;
  traceRunId: string;
  companionName: string;
  onConnectionChange: (traceRunId: string, connected: boolean) => void;
  onStatus: (traceRunId: string, status: ConversationTurnLifecycleStatus) => void;
  onResponsePersisted: () => Promise<void>;
}) {
  const [content, setContent] = useState("");
  const [persisted, setPersisted] = useState(false);
  const pendingChunksRef = useRef<string[]>([]);
  const flushFrameRef = useRef<number | null>(null);
  const responseReconciledRef = useRef(false);

  useEffect(() => {
    const stream = new EventSource(conversationTurnEventUrl(conversationId, traceRunId, companionId));
    const flushChunks = () => {
      flushFrameRef.current = null;
      if (!pendingChunksRef.current.length) return;
      const next = pendingChunksRef.current.join("");
      pendingChunksRef.current = [];
      setContent((current) => current + next);
    };
    const scheduleFlush = () => {
      if (flushFrameRef.current === null) {
        flushFrameRef.current = window.requestAnimationFrame(flushChunks);
      }
    };
    const onDelta = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as { delta?: string };
        if (payload.delta) {
          pendingChunksRef.current.push(payload.delta);
          scheduleFlush();
        }
      } catch { /* Ignore a malformed transient event; durable status remains authoritative. */ }
    };
    const readStatus = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as {
          status?: ConversationTurnLifecycleStatus | { status?: ConversationTurnLifecycleStatus };
        };
        const status = typeof payload.status === "string" ? payload.status : payload.status?.status;
        if (status) onStatus(traceRunId, status);
        return status;
      } catch { /* Durable fallback polling resumes if the event is malformed. */ }
      return undefined;
    };
    const reconcileCanonicalResponse = () => {
      if (responseReconciledRef.current) return;
      responseReconciledRef.current = true;
      flushChunks();
      void onResponsePersisted()
        .then(() => setPersisted(true))
        .catch(() => {
          responseReconciledRef.current = false;
          onConnectionChange(traceRunId, false);
        });
    };
    const reconcileResponse = (event: MessageEvent<string>) => {
      readStatus(event);
      reconcileCanonicalResponse();
    };
    const readSnapshot = (event: MessageEvent<string>) => {
      const status = readStatus(event);
      if (status && ["response_persisted", "effects_processing", "completed", "cancelled"].includes(status)) {
        reconcileCanonicalResponse();
      }
    };
    const readTerminal = (event: MessageEvent<string>) => {
      const status = readStatus(event);
      if (status === "completed" || status === "cancelled") reconcileCanonicalResponse();
    };
    const handleOpen = () => onConnectionChange(traceRunId, true);
    const handleError = () => onConnectionChange(traceRunId, false);
    stream.addEventListener("open", handleOpen);
    stream.addEventListener("error", handleError);
    stream.addEventListener("delta", onDelta as EventListener);
    stream.addEventListener("snapshot", readSnapshot as EventListener);
    stream.addEventListener("lifecycle", readStatus as EventListener);
    stream.addEventListener("response_persisted", reconcileResponse as EventListener);
    stream.addEventListener("completed", readTerminal as EventListener);
    stream.addEventListener("failed", readStatus as EventListener);
    stream.addEventListener("cancelled", readTerminal as EventListener);
    return () => {
      stream.close();
      onConnectionChange(traceRunId, false);
      if (flushFrameRef.current !== null) window.cancelAnimationFrame(flushFrameRef.current);
    };
  }, [companionId, conversationId, onConnectionChange, onResponsePersisted, onStatus, traceRunId]);

  if (persisted || !content) return null;
  return <article className="conversation-message is-assistant is-streaming" aria-label={`${companionName} 正在回应`}><div className="conversation-message-body"><small>{companionName} · 正在回应</small><ConversationMessageContent content={content} markdown={false} /><span className="conversation-stream-caret" aria-hidden="true" /></div></article>;
}

const toolStatusCopy: Record<ToolRun["status"], string> = {
  planned: "已规划", awaiting_input: "等待补充", awaiting_confirmation: "等待确认", queued: "已排队",
  running: "执行中", retry_scheduled: "等待重试", succeeded: "已完成", failed: "失败",
  cancelled: "已取消", blocked: "已阻止", timed_out: "已超时",
};

const taskStatusCopy: Record<ConversationTaskRun["status"], string> = {
  draft: "草拟中",
  awaiting_input: "等待补充",
  awaiting_approval: "等待确认",
  ready: "准备执行",
  running: "执行中",
  paused: "已暂停",
  blocked: "已阻止",
  completed: "已完成",
  cancelled: "已取消",
  failed: "失败",
};

function TaskActivityPanel({
  task,
  toolRuns,
  loading,
  error,
  selected,
  taskBusy,
  taskError,
  toolBusy,
  toolError,
  onTaskAction,
  onToolAction,
}: {
  task: ConversationTaskRun | null;
  toolRuns: ToolRun[];
  loading: boolean;
  error: boolean;
  selected: boolean;
  taskBusy: boolean;
  taskError: Error | null;
  toolBusy: boolean;
  toolError: Error | null;
  onTaskAction: (task: ConversationTaskRun, action: "pause" | "resume" | "cancel") => void;
  onToolAction: (run: ToolRun, action: "confirm" | "cancel" | "retry") => void;
}) {
  if (!selected) return <div className="conversation-panel-content"><DataState kind="empty" title="请选择一条伙伴回复" description="本轮活动只展示与所选回复精确绑定的任务和工具。" /></div>;
  if (loading) return <div className="conversation-panel-content"><DataState kind="loading" title="正在读取本轮活动" description="正在核对回复、任务和工具运行的真实绑定。" /></div>;
  if (error) return <div className="conversation-panel-content"><DataState kind="empty" title="这条历史回复没有可恢复的活动" description="旧回复可能没有消息级活动记录；系统不会改用整个对话的工具列表替代。" /></div>;
  return <div className="conversation-panel-content task-activity-panel">
    <p className="conversation-panel-scope"><b>所选伙伴回复</b><span>这里只显示与这条回复的真实运行记录精确绑定的活动</span></p>
    <section className="task-activity-domain">
      <small>多步任务</small>
      {task
        ? <ConversationTaskCard task={task} busy={taskBusy} error={taskError} onAction={(action) => onTaskAction(task, action)} />
        : <DataState kind="empty" title="本轮没有创建或推进任务" description="普通陪伴回复不会被包装成任务。" />}
    </section>
    <section className="task-tool-activity">
      <small>本轮工具活动</small>
      <p>这里只展示所选回复实际使用的工具；结果摘要直接展示，技术载荷默认折叠。</p>
      {toolRuns.length
        ? toolRuns.slice(0, 6).map((run) => <ToolRunCard key={run.id} run={run} busy={toolBusy} error={toolError} onAction={(action) => onToolAction(run, action)} />)
        : <DataState kind="empty" title="尚无工具活动" description="当伙伴调用搜索、天气、提醒、笔记等工具后，过程和结果会出现在这里。" />}
    </section>
  </div>;
}

function ConversationTaskCard({
  task,
  busy,
  error,
  onAction,
}: {
  task: ConversationTaskRun;
  busy: boolean;
  error: Error | null;
  onAction: (action: "pause" | "resume" | "cancel") => void;
}) {
  const completed = task.steps.filter((step) => step.status === "succeeded").length;
  const waiting = task.steps.filter((step) => ["awaiting_input", "awaiting_approval"].includes(step.status)).length;
  const failed = task.steps.filter((step) => ["failed", "blocked"].includes(step.status)).length;
  const evidenceCount = task.steps.reduce((count, step) => count + step.evidence_refs.length, 0);
  const current = task.steps.find((step) => step.order === task.current_step_order)
    ?? task.steps.find((step) => !["succeeded", "cancelled", "skipped"].includes(step.status));
  const terminal = ["completed", "cancelled", "failed"].includes(task.status);
  const acceptanceLabel = task.acceptance_state === "verified"
    ? "验收通过"
    : task.acceptance_state === "rejected"
      ? "验收未通过"
      : task.acceptance_state === "not_applicable"
        ? "无需独立验收"
        : "等待验收";
  return <section className={`conversation-task-card is-${task.status}`} aria-label={`任务：${task.goal}`}>
    <header>
      <span><ListChecks size={17} aria-hidden="true" /><strong>任务</strong></span>
      <em>{taskStatusCopy[task.status]}</em>
    </header>
    <h3>{task.goal}</h3>
    <p className="conversation-task-current">
      {current ? `当前：${current.order}. ${current.title}` : "当前没有待执行步骤"}
    </p>
    <div className="conversation-task-counts" aria-label="任务步骤统计">
      <span>完成 <b>{completed}</b></span>
      <span>待确认/补充 <b>{waiting}</b></span>
      <span>失败/阻止 <b>{failed}</b></span>
    </div>
    <details className="conversation-task-disclosure" open={!terminal}>
      <summary>查看计划、预算与证据</summary>
      <ol>
        {task.steps.map((step) => <li key={step.id} className={`is-${step.status}`}>
          <span>{step.order}</span>
          <div><strong>{step.title}</strong><small>{step.executor_type === "tool" ? toolCapabilityLabel(step.capability) : step.executor_type === "research" ? "只读研究" : "验收"} · {step.status}</small></div>
        </li>)}
      </ol>
      <footer>
        <span>{acceptanceLabel} · 计划 v{task.plan_version} · Replan {task.budgets.replan_count}/{task.budgets.max_replans} · 工具 {task.budgets.tool_run_count}/{task.budgets.max_tool_runs} · {evidenceCount} 条证据引用</span>
      </footer>
    </details>
    {task.status === "blocked" || task.status === "awaiting_input" ? <p className="conversation-task-next-action">你可以在输入框补充或修正目标，伙伴会创建新的修复步骤并保留已有证据；也可以停止这个任务。</p> : null}
    {!terminal ? <div className="conversation-task-actions">
      {task.status === "blocked" || task.status === "awaiting_input"
        ? null
        : task.status === "paused"
        ? <button type="button" disabled={busy} onClick={() => onAction("resume")}><Play size={15} />恢复任务</button>
        : <button type="button" disabled={busy} onClick={() => onAction("pause")}><Pause size={15} />暂停</button>}
      <button type="button" disabled={busy} onClick={() => onAction("cancel")}><X size={15} />取消任务</button>
    </div> : null}
    {error ? <small role="alert">{error.message}</small> : null}
  </section>;
}

function ToolRunCard({ run, busy, error, onAction }: { run: ToolRun; busy: boolean; error: Error | null; onAction: (action: "confirm" | "cancel" | "retry") => void }) {
  const missing = Array.isArray(run.error_json.missing_fields) ? run.error_json.missing_fields.join("、") : "";
  const errorMessage = typeof run.error_json.message === "string" ? run.error_json.message : null;
  const canRetry = run.requested_by !== "conversation_task" && ["failed", "timed_out", "retry_scheduled"].includes(run.status) && run.attempt_count < run.max_attempts;
  return <section className={`conversation-tool-card is-${run.status}`} aria-label={`${run.capability || "工具"}运行状态`}>
    <header><span><Wrench size={16} aria-hidden="true" /><strong>{toolCapabilityLabel(run.capability)}</strong></span><em>{toolStatusCopy[run.status]}</em></header>
    <details className="conversation-tool-disclosure" open>
      <summary>{run.status === "succeeded" ? toolResultHeadline(run.capability, run.output_json) : "查看本次工具活动"}</summary>
      <div className="conversation-tool-disclosure-body">
        {run.confirmation_summary ? <p>{run.confirmation_summary}</p> : null}
        {missing ? <p>还需要：{missing}</p> : null}
        {errorMessage ? <p className="conversation-tool-error">{errorMessage}</p> : null}
        {Object.keys(run.output_json).length ? <ToolOutputSummary capability={run.capability} output={run.output_json} /> : null}
        {Object.keys(run.output_json).length || Object.keys(run.error_json).length ? <details className="conversation-tool-technical"><summary>技术详情</summary><pre>{JSON.stringify(Object.keys(run.output_json).length ? run.output_json : run.error_json, null, 2)}</pre></details> : null}
      </div>
    </details>
    <footer><span>已执行 {run.attempt_count} 次 · 上限 {run.max_attempts} 次 · {run.evidence_refs.length} 条证据</span><div>
      {run.status === "awaiting_confirmation" ? <><button type="button" disabled={busy} onClick={() => onAction("confirm")}><Check size={15} />确认执行</button><button type="button" disabled={busy} onClick={() => onAction("cancel")}><X size={15} />取消</button></> : null}
      {canRetry ? <button type="button" disabled={busy} onClick={() => onAction("retry")}><RotateCcw size={15} />重试</button> : null}
    </div></footer>
    {error ? <small role="alert">{error.message}</small> : null}
  </section>;
}

function ToolResultMessage({ message }: { message: MessageBrief }) {
  type PersistedToolResult = { capability?: string; status?: string; output?: Record<string, unknown> };
  let result: PersistedToolResult | null = null;
  try { result = JSON.parse(message.content) as PersistedToolResult; } catch { /* Persisted historical payload stays safely opaque. */ }
  return <article id={`conversation-message-${message.id}`} data-message-id={message.id} className="conversation-message is-tool"><div className="conversation-tool-result"><small><Wrench size={14} />工具结果</small><strong>{toolCapabilityLabel(result?.capability)} · {result?.status || "已记录"}</strong><details className="conversation-tool-disclosure"><summary>{result?.output ? toolResultHeadline(result.capability, result.output) : "查看已保存结果"}</summary><div className="conversation-tool-disclosure-body">{result?.output ? <><ToolOutputSummary capability={result.capability} output={result.output} /><details className="conversation-tool-technical"><summary>技术详情</summary><pre>{JSON.stringify(result.output, null, 2)}</pre></details></> : <p>结果已保存，但当前记录不是可展示的结构化格式。</p>}</div></details></div></article>;
}

const toolCapabilityLabels: Record<string, string> = {
  weather: "天气",
  search: "搜索",
  web_read: "网页读取",
  reminder: "提醒",
  calendar: "日程",
  translation: "翻译",
  exchange: "汇率换算",
  note: "笔记",
  file: "文件",
};

const toolFieldLabels: Record<string, string> = {
  location: "地点",
  country: "国家或地区",
  admin1: "一级行政区",
  date: "日期",
  timezone: "地点时区",
  data_route: "数据类型",
  temperature_max_c: "最高温",
  temperature_min_c: "最低温",
  precipitation_probability_percent: "降水概率",
  precipitation_sum_mm: "降水量",
  wind_speed_max_kmh: "最大风速",
  source_currency: "原币种",
  target_currency: "目标币种",
  amount: "金额",
  converted_amount: "换算结果",
  translated_text: "译文",
  title: "标题",
  due_at: "时间",
};

function toolCapabilityLabel(capability?: string | null) {
  return capability ? toolCapabilityLabels[capability] || capability : "受控工具";
}

function toolResultHeadline(capability: string | null | undefined, output: Record<string, unknown>) {
  if (capability === "weather") {
    const location = String(output.location || "所选地点");
    const date = output.date ? ` · ${String(output.date)}` : "";
    const maximum = output.temperature_max_c;
    const minimum = output.temperature_min_c;
    const temperatures = maximum !== undefined && minimum !== undefined ? ` · ${String(minimum)}–${String(maximum)}℃` : "";
    return `${location}${date}${temperatures}`;
  }
  if (capability === "translation" && output.translated_text) return String(output.translated_text).slice(0, 90);
  if (capability === "exchange" && output.converted_amount !== undefined) return `换算结果：${String(output.converted_amount)} ${String(output.target_currency || "")}`.trim();
  return "查看工具结果";
}

function ToolOutputSummary({ capability, output }: { capability?: string | null; output: Record<string, unknown> }) {
  const hiddenFields = new Set(["weather_code"]);
  const entries = Object.entries(output)
    .filter(([key, value]) => !hiddenFields.has(key) && value !== null && value !== undefined && typeof value !== "object")
    .slice(0, 12);
  if (!entries.length) return <p>工具已经返回结构化结果，可在技术详情中查看。</p>;
  return <dl className={`conversation-tool-summary is-${capability || "generic"}`}>
    {entries.map(([key, value]) => <div key={key}><dt>{toolFieldLabels[key] || key.replaceAll("_", " ")}</dt><dd>{formatToolValue(key, value)}</dd></div>)}
  </dl>;
}

function formatToolValue(key: string, value: unknown) {
  if (key === "temperature_max_c" || key === "temperature_min_c") return `${String(value)}℃`;
  if (key === "precipitation_probability_percent") return `${String(value)}%`;
  if (key === "precipitation_sum_mm") return `${String(value)} mm`;
  if (key === "wind_speed_max_kmh") return `${String(value)} km/h`;
  if (key === "data_route") return value === "archive" ? "历史天气" : "预报与近期天气";
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function ContextPanel({ evidence, loading, error, selected }: { evidence?: ConversationMessageEvidence; loading: boolean; error: boolean; selected: boolean }) {
  if (!selected) return <div className="conversation-panel-content"><DataState kind="empty" title="请选择一条伙伴回复" description="本轮上下文只展示生成所选回复前实际采用的信息。" /></div>;
  if (loading) return <div className="conversation-panel-content"><DataState kind="loading" title="正在恢复本轮上下文" description="正在读取与这条回复精确绑定的 Context Pack 记录。" /></div>;
  if (error || !evidence) return <div className="conversation-panel-content"><DataState kind="empty" title="这条历史回复没有可恢复的上下文" description="旧回复可能没有保存 Context Pack；系统不会使用伙伴当前状态补造。" /></div>;
  const pack = evidence.context.pack;
  const included = pack.sections.filter((section) => section.included);
  const excluded = pack.sections.filter((section) => !section.included);
  const memories = evidence.context.memories.selected;
  return <div className="conversation-panel-content context-pack-panel">
    <p className="conversation-panel-scope"><b>所选伙伴回复</b><span>以下内容是生成这条回复之前实际准备的信息，不是整个对话的摘要</span></p>
    <section><small>本轮回应的内容</small><h3>{pack.input_summary || evidence.context.conversation.current_goal || evidence.context.conversation.current_topic || evidence.context.conversation.title}</h3><p>{pack.recent_message_count != null ? `同时纳入了最近 ${pack.recent_message_count} 条同一对话消息。` : "最近对话范围没有可展示的计数记录。"}</p></section>
    <section><small>实际进入本轮的信息</small>{included.length ? <div className="context-pack-section-list">{included.map((section) => <span key={section.key}><Check size={14} aria-hidden="true" /><strong>{section.label}</strong><small>{section.explanation}</small></span>)}</div> : <p>这条历史回复没有保存可展示的 Context Pack 分区记录。</p>}</section>
    <section><small>实际采用的长期记忆</small>{memories.length ? memories.map((memory) => <p key={memory.id}><strong>{memory.summary}</strong>{memory.updated_at ? ` · 更新于 ${new Date(memory.updated_at).toLocaleDateString("zh-CN")}` : ""}</p>) : <p>本轮没有采用长期记忆，主要依据当前对话内容。</p>}</section>
    {excluded.length ? <details className="conversation-advanced-details"><summary>查看本轮未纳入的信息</summary><div className="context-pack-section-list is-excluded">{excluded.map((section) => <span key={section.key}><X size={14} aria-hidden="true" /><strong>{section.label}</strong><small>{section.explanation}</small></span>)}</div></details> : null}
  </div>;
}

function ReviewPanel({ companionId, conversationId, memories, growth, companionReviewCount, reviewCounts }: { companionId: string; conversationId: string; memories: MemoryCandidate[]; growth: GrowthCandidate[]; companionReviewCount: number; reviewCounts: Record<string, number> }) {
  const queryClient = useQueryClient();
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["memory-candidates", companionId] }), queryClient.invalidateQueries({ queryKey: ["growth-candidates", companionId] }), queryClient.invalidateQueries({ queryKey: ["companions", companionId, "workspace"] })]);
  const categoryCount = (keys: string[]) => keys.reduce((sum, key) => sum + (reviewCounts[key] ?? 0), 0);
  const returnTo = `/companions/${companionId}/conversations/${conversationId}`;
  return <div className="conversation-panel-content review-list">
    <section className="review-scope-summary"><small>当前对话</small><h3>{memories.length + growth.length} 项需要决定</h3><p>这里只显示能由真实来源字段确认属于当前对话的记忆与成长候选。接受后会写入当前伙伴的私有状态；确认前不会生效。关系、共享与频道内容当前只提供伙伴完整队列计数，不推定为本对话来源。</p><div className="review-category-grid"><span>记忆（当前对话） <b>{memories.length}</b></span><span>成长（当前对话） <b>{growth.length}</b></span><span>关系（伙伴队列） <b>{categoryCount(["relationship", "persona_growth"])}</b></span><span>共享 / 频道（伙伴队列） <b>{categoryCount(["private_to_shared", "shared_to_private", "cross_companion", "channel", "realtime_shared"])}</b></span></div></section>
    {!memories.length && !growth.length ? <DataState kind="empty" title="当前对话没有待确认内容" description={companionReviewCount ? `伙伴完整队列仍有 ${companionReviewCount} 项；它们不一定来自当前对话。` : "只有真实候选产生时，这里才会要求你的决定。"} /> : null}
    {memories.map((candidate) => <MemoryReviewCard key={candidate.id} candidate={candidate} onDone={refresh} />)}
    {growth.map((candidate) => <GrowthReviewCard key={candidate.id} candidate={candidate} onDone={refresh} />)}
    <Link className="review-queue-link" href={`/settings/review?return_to=${encodeURIComponent(returnTo)}`}><ShieldCheck size={16} /><span>打开伙伴完整确认队列</span><b>{companionReviewCount}</b></Link>
  </div>;
}

function MemoryReviewCard({ candidate, onDone }: { candidate: MemoryCandidate; onDone: () => Promise<unknown> }) {
  const [content, setContent] = useState(candidate.content);
  const [status, setStatus] = useState(candidate.status);
  const action = useMutation({ mutationFn: async (kind: "accept" | "commit" | "edit" | "reject") => { if (kind === "accept") { await acceptCandidate(candidate.id); setStatus("accepted"); return; } if (kind === "commit") { await commitCandidate(candidate.id); setStatus("committed"); return; } if (kind === "edit") { await editCandidate(candidate.id, { content, accept_after_edit: true }); setStatus("committed"); return; } await rejectCandidate(candidate.id, { reason: "用户在本轮审核中拒绝" }); setStatus("rejected"); }, onSuccess: (_, kind) => kind === "accept" ? undefined : onDone() });
  return <article className="review-card"><header><span>待确认记忆</span><b>{candidate.suggested_type || "长期记忆"}</b></header><textarea value={content} onChange={(event) => setContent(event.target.value)} aria-label="编辑候选记忆" disabled={status !== "pending"} /><p>目标 owner：当前 Companion 私有空间</p><div>{status === "pending" ? <><button onClick={() => action.mutate("reject")} disabled={action.isPending}>拒绝</button><button onClick={() => action.mutate(content === candidate.content ? "accept" : "edit")} disabled={action.isPending}>{content === candidate.content ? "接受" : "编辑并写入"}</button></> : null}{status === "accepted" ? <button className="is-primary" onClick={() => action.mutate("commit")} disabled={action.isPending}><Check size={15} />确认写入记忆</button> : null}{status === "committed" ? <span className="review-success"><Check size={15} />已写入长期记忆</span> : null}</div></article>;
}

function GrowthReviewCard({ candidate, onDone }: { candidate: GrowthCandidate; onDone: () => Promise<unknown> }) {
  const action = useMutation({ mutationFn: (kind: "commit" | "reject") => kind === "commit" ? commitGrowth(candidate.id) : rejectGrowth(candidate.id, { reason: "用户在本轮审核中拒绝" }), onSuccess: onDone });
  const impactCount = Object.keys(candidate.profile_patch_preview ?? {}).length;
  return <article className="review-card"><header><span>待确认成长</span><b>{candidate.risk_level || "低风险"}</b></header><h3>{candidate.content || "伙伴成长建议"}</h3><p>影响预览：{impactCount ? `将调整 ${impactCount} 个已声明的伙伴档案字段，确认前不会生效。` : "不会自动改写人格；确认后才应用。"}</p><div><button onClick={() => action.mutate("reject")} disabled={action.isPending}>拒绝</button><button className="is-primary" onClick={() => action.mutate("commit")} disabled={action.isPending}>确认成长</button></div></article>;
}

function WhyPanel({ evidence, loading, error, selected, onTrace }: { evidence?: ConversationMessageEvidence; loading: boolean; error: boolean; selected: boolean; onTrace: () => void }) {
  if (!selected) return <div className="conversation-panel-content"><DataState kind="empty" title="请选择一条伙伴回复" description="点击任意历史伙伴消息下方的“回复依据”，即可查看与该回复精确绑定的事实和边界。" /></div>;
  if (loading) return <div className="conversation-panel-content"><DataState kind="loading" title="正在恢复这条回复的依据" description="正在核对 Conversation、Companion、Message 与 Trace 的一致性。" /></div>;
  if (error || !evidence) return <div className="conversation-panel-content"><DataState kind="empty" title="这条历史回复没有可恢复的依据" description="旧消息可能没有绑定 Trace；系统不会改用伙伴范围的最新记录来猜测。" /></div>;
  const mode = evidence.response.provider_mode;
  const memories = evidence.context.memories;
  const tools = evidence.tools.runs;
  const blockingBoundaries = evidence.boundaries.filter((item) => item.outcome === "blocked");
  return <div className="conversation-panel-content evidence-panel">
    <p className="conversation-panel-scope"><b>所选伙伴回复</b><span>所有内容都与这条回复及其真实运行记录精确绑定，不代表整个对话</span></p>
    <section><small>这条回复在回应什么</small><h3>{evidence.context.pack.input_summary || evidence.context.conversation.current_goal || evidence.context.conversation.current_topic || evidence.context.conversation.title}</h3><p>{evidence.response.generation_status === "interrupted" ? "这是一条被你停止后保留的部分回复。" : evidence.context.pack.input_summary ? "这是生成该回复时保存的本轮输入摘要。" : "这条历史回复没有保存本轮输入摘要，当前显示对话主题作为辅助说明。"}</p></section>
    <section><small>使用的记忆</small>{memories.selected.length ? memories.selected.map((memory) => <p key={memory.id}>{memory.summary}</p>) : <p>没有使用长期记忆，主要依据当前对话内容。</p>}</section>
    <section><small>工具与外部结果</small>{tools.length ? <div className="evidence-tool-results">{tools.map((run) => <div key={run.id}><span><Wrench size={15} aria-hidden="true" /><strong>{toolCapabilityLabel(run.capability)}</strong><em>{toolStatusCopy[run.status]}</em></span>{Object.keys(run.output_json).length ? <><p>{toolResultHeadline(run.capability, run.output_json)}</p><ToolOutputSummary capability={run.capability} output={run.output_json} /></> : <p>{run.confirmation_summary || "本轮记录了工具活动，但没有可展示的结果。"}</p>}</div>)}</div> : <p>本轮没有使用工具或外部结果。</p>}{evidence.activity.task_run_id ? <p>本轮还创建或推进了一个多步任务，可在“本轮活动”中查看。</p> : null}</section>
    {blockingBoundaries.length ? <section><small>影响本轮的安全限制</small>{blockingBoundaries.map((item) => <p key={item.key}><strong>{item.label}</strong>：已阻止相关内容进入回复。</p>)}</section> : null}
    <section><small>不确定与待处理内容</small><p>{evidence.post_turn.error_count ? `回复后的整理有 ${evidence.post_turn.error_count} 项未完成，不影响已保存的回复。` : "没有记录影响这条回复可信度的后续失败。"}</p><p>{evidence.decisions.memory_candidates + evidence.decisions.growth_candidates ? "本轮形成了待你确认的记忆或成长候选；确认前不会生效。" : "本轮没有需要你确认的记忆或成长变化。"}</p></section>
    <section><small>关系变化说明</small>{evidence.relationship_explanations.length ? evidence.relationship_explanations.map((item) => <div key={item.id}><h3>{item.title || "关系理解发生变化"}</h3><p>{item.explanation}</p></div>) : <p>这条回复没有与其 Trace 精确绑定的可见关系变化说明。</p>}</section>
    <details className="conversation-advanced-details"><summary>高级运行信息</summary><p>{mode === "mock" ? "历史模拟路径" : "真实 Provider"} · {evidence.response.provider_name || "Provider 未记录"}{evidence.response.model_name ? ` · ${evidence.response.model_name}` : ""}</p>{evidence.response.provider_timing.total_ms ? <p>总耗时 {evidence.response.provider_timing.total_ms} ms{evidence.response.provider_timing.time_to_first_token_ms != null ? ` · 首 token ${evidence.response.provider_timing.time_to_first_token_ms} ms` : ""}</p> : null}<p>记忆检索 {memories.retrieved_count ?? "未记录"} 条，纳入 {memories.selected_count ?? 0} 条，排除 {memories.excluded_count ?? "未记录"} 条。</p></details>
    <button className="why-trace-button" onClick={onTrace}><FileClock size={16} aria-hidden="true" />查看这次回应的过程</button>
  </div>;
}
