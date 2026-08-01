"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Bug,
  CheckCircle2,
  FlaskConical,
  GitCompareArrows,
  Network,
  PlayCircle,
  ShieldCheck,
} from "lucide-react";
import { ConfirmActionDialog } from "@/components/patterns/ConfirmActionDialog";
import { DataState } from "@/components/patterns/DataState";
import { DETAIL_PAGE_SIZE, Pagination, usePageParam } from "@/components/patterns/Pagination";
import { listStudio } from "@/lib/api/studio";
import { createReplayFromTrace, createReplayBadCase, createReplayRegressionCase } from "@/lib/api/replays";
import { convertInboxItemToBadCase, convertInboxItemToRegressionCase } from "@/lib/api/badCaseInbox";
import { createEvaluationResultBadCase } from "@/lib/api/evaluation";
import { createRegressionResultBadCase } from "@/lib/api/regression";

type QualityView = "trace" | "replay" | "bad-cases" | "evaluation" | "regression";
type Item = Record<string, unknown>;
type PendingAction =
  | { kind: "trace-replay"; id: string }
  | { kind: "replay-bad-case"; id: string }
  | { kind: "replay-regression"; id: string }
  | { kind: "bad-case-convert"; id: string; target: "bad-case" | "regression" }
  | { kind: "evaluation-bad-case"; id: string }
  | { kind: "regression-bad-case"; id: string };

const viewCopy: Record<QualityView, { label: string; title: string; description: string; icon: typeof Network; empty: string }> = {
  trace: {
    label: "Trace",
    title: "Trace 调查",
    description: "从真实运行记录进入决策节点、边界判断、Provider 与证据链。",
    icon: Network,
    empty: "暂无可读取的 Trace。",
  },
  replay: {
    label: "Replay",
    title: "Replay 对照",
    description: "保留输入、步骤、输出和差异标注，用于复核与后续质量闭环。",
    icon: PlayCircle,
    empty: "暂无可回放记录。",
  },
  "bad-cases": {
    label: "Bad Case",
    title: "Bad Case 分诊",
    description: "按失败类型、严重度、可复现性和处置状态组织诊断。",
    icon: Bug,
    empty: "暂无待分诊 Bad Case。",
  },
  evaluation: {
    label: "Evaluation",
    title: "评测运行",
    description: "查看数据集、评测运行、指标、失败样本和 gate 证据。",
    icon: FlaskConical,
    empty: "暂无评测运行或结果。",
  },
  regression: {
    label: "Regression",
    title: "回归运行",
    description: "查看回归用例、运行状态、差异结果和失败证据。",
    icon: GitCompareArrows,
    empty: "暂无回归运行或结果。",
  },
};

function text(item: Item | undefined, keys: string[], fallback = "—") {
  if (!item) return fallback;
  for (const key of keys) {
    const value = item[key];
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number" || typeof value === "boolean") return String(value);
  }
  return fallback;
}

function titleOf(item: Item) {
  return text(item, ["title", "name", "agent_graph_name", "summary", "case_type", "status", "id"], "质量记录");
}

function timeOf(item: Item) {
  const value = text(item, ["created_at", "updated_at"], "");
  if (!value) return "来自当前真实记录";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
}

function statusOf(item: Item) {
  return text(item, ["status", "run_status", "result_status", "severity", "replay_type"], "已记录");
}

function summaryOf(view: QualityView, item: Item) {
  if (view === "trace") return text(item, ["input_summary", "output_summary", "summary", "agent_graph_name"], "该 Trace 保留运行步骤与决策证据。");
  if (view === "replay") return text(item, ["summary", "trace_run_id", "replay_type"], "该 Replay 可继续转入 Bad Case 或 Regression。");
  if (view === "bad-cases") return text(item, ["description", "case_type", "source_type"], "该 Bad Case 等待分诊或转换为后续验证资产。");
  if (view === "evaluation") return text(item, ["judge_reason", "dataset_id", "judge_type"], "该评测记录可追踪运行结果与失败样本。");
  return text(item, ["failure_reason", "case_type", "expected_behavior"], "该回归记录保留失败原因或通过状态。");
}

function idOf(item: Item) {
  return text(item, ["id"], "");
}

function useQualityData(view: QualityView, page: number) {
  const pageFor = (entry: QualityView) => view === entry ? page : 1;
  const traces = useQuery({ queryKey: ["quality", "traces", pageFor("trace")], queryFn: () => listStudio<Item>("/traces", { page: pageFor("trace"), page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const replays = useQuery({ queryKey: ["quality", "replays", pageFor("replay")], queryFn: () => listStudio<Item>("/replays", { page: pageFor("replay"), page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const badCases = useQuery({ queryKey: ["quality", "bad-cases", pageFor("bad-cases")], queryFn: () => listStudio<Item>("/bad-case-inbox", { page: pageFor("bad-cases"), page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const evaluationRuns = useQuery({ queryKey: ["quality", "evaluation-runs", pageFor("evaluation")], queryFn: () => listStudio<Item>("/evaluation-runs", { page: pageFor("evaluation"), page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });
  const regressionRuns = useQuery({ queryKey: ["quality", "regression-runs", pageFor("regression")], queryFn: () => listStudio<Item>("/regression-runs", { page: pageFor("regression"), page_size: DETAIL_PAGE_SIZE }), staleTime: 15_000 });

  return useMemo(() => {
    const byView = {
      trace: { primary: traces, items: traces.data?.items ?? [] },
      replay: { primary: replays, items: replays.data?.items ?? [] },
      "bad-cases": { primary: badCases, items: badCases.data?.items ?? [] },
      evaluation: { primary: evaluationRuns, items: evaluationRuns.data?.items ?? [] },
      regression: { primary: regressionRuns, items: regressionRuns.data?.items ?? [] },
    } satisfies Record<QualityView, { primary: typeof traces; items: Item[] }>;
    const active = byView[view];
    const all = [traces, replays, badCases, evaluationRuns, regressionRuns];
    return {
      ...active,
      pagination: active.primary.data?.pagination,
      isLoading: active.primary.isLoading,
      isError: active.primary.isError,
      partial: all.some((query) => query.isLoading || query.isError),
      refetchAll: () => Promise.all(all.map((query) => query.refetch())),
      counts: {
        trace: traces.data?.pagination.total ?? 0,
        replay: replays.data?.pagination.total ?? 0,
        "bad-cases": badCases.data?.pagination.total ?? 0,
        evaluation: evaluationRuns.data?.pagination.total ?? 0,
        regression: regressionRuns.data?.pagination.total ?? 0,
      },
    };
  }, [badCases, evaluationRuns, regressionRuns, replays, traces, view]);
}

function routeView(route: QualityView, query: string | null): QualityView {
  if (route === "evaluation" && query === "regression") return "regression";
  return route;
}

function actionCopy(action: PendingAction) {
  if (action.kind === "trace-replay") return { title: "从 Trace 创建 Replay", label: "创建 Replay", description: "将保存该 Trace 的输入、步骤与输出快照，用于后续回放和质量审查。" };
  if (action.kind === "replay-bad-case") return { title: "标记为 Bad Case", label: "创建 Bad Case", description: "将从该 Replay 创建一条待分诊 Bad Case，并保留 Trace 关联。" };
  if (action.kind === "replay-regression") return { title: "创建回归用例", label: "创建 Regression", description: "将从该 Replay 创建一条回归用例，供后续质量验证。" };
  if (action.kind === "bad-case-convert" && action.target === "regression") return { title: "转为回归用例", label: "创建 Regression", description: "将该 Bad Case 转换为回归用例，保留失败上下文。" };
  if (action.kind === "bad-case-convert") return { title: "归档为 Bad Case", label: "创建 Bad Case", description: "将收件箱条目转换为可追踪 Bad Case 记录。" };
  return { title: "生成失败样本", label: "创建 Bad Case", description: "将当前结果转入 Bad Case 分诊，不改变原始评测或回归记录。" };
}

export function QualityWorkspace({ route }: { route: QualityView }) {
  const searchParams = useSearchParams();
  const view = routeView(route, searchParams.get("view"));
  const [page, setPage] = usePageParam();
  const [resultPage, setResultPage] = usePageParam("result_page");
  const copy = viewCopy[view];
  const Icon = copy.icon;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const data = useQualityData(view, page);
  const selected = data.items.find((item) => idOf(item) === selectedId) ?? data.items[0] ?? null;
  const resultPath = view === "evaluation" ? "/evaluation-results" : "/regression-results";
  const resultFilter = view === "evaluation" ? "evaluation_run_id" : "regression_run_id";
  const resultQuery = useQuery({
    queryKey: ["quality", `${view}-results`, idOf(selected ?? {}), resultPage],
    queryFn: () => listStudio<Item>(resultPath, { page: resultPage, page_size: DETAIL_PAGE_SIZE, [resultFilter]: idOf(selected ?? {}) }),
    enabled: (view === "evaluation" || view === "regression") && Boolean(selected),
    staleTime: 15_000,
  });

  async function confirmAction() {
    if (!pending) return;
    setSaving(true);
    setActionError(null);
    try {
      if (pending.kind === "trace-replay") await createReplayFromTrace(pending.id);
      if (pending.kind === "replay-bad-case") await createReplayBadCase(pending.id);
      if (pending.kind === "replay-regression") await createReplayRegressionCase(pending.id);
      if (pending.kind === "bad-case-convert" && pending.target === "bad-case") await convertInboxItemToBadCase(pending.id);
      if (pending.kind === "bad-case-convert" && pending.target === "regression") await convertInboxItemToRegressionCase(pending.id);
      if (pending.kind === "evaluation-bad-case") await createEvaluationResultBadCase(pending.id);
      if (pending.kind === "regression-bad-case") await createRegressionResultBadCase(pending.id);
      await data.refetchAll();
      if (view === "evaluation" || view === "regression") await resultQuery.refetch();
      setPending(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "质量操作未能保存，请检查当前 Agent API 后重试。");
    } finally {
      setSaving(false);
    }
  }

  function actionsFor(item: Item) {
    const id = idOf(item);
    if (!id) return null;
    if (view === "trace") return <button type="button" onClick={() => setPending({ kind: "trace-replay", id })}><PlayCircle size={15} />创建 Replay</button>;
    if (view === "replay") return <><button type="button" onClick={() => setPending({ kind: "replay-bad-case", id })}><Bug size={15} />Bad Case</button><button type="button" onClick={() => setPending({ kind: "replay-regression", id })}><GitCompareArrows size={15} />Regression</button></>;
    if (view === "bad-cases") return <><button type="button" onClick={() => setPending({ kind: "bad-case-convert", id, target: "bad-case" })}>归档 Bad Case</button><button type="button" onClick={() => setPending({ kind: "bad-case-convert", id, target: "regression" })}>转回归</button></>;
    if (view === "evaluation") return <button type="button" onClick={() => setPending({ kind: "evaluation-bad-case", id })}><Bug size={15} />失败样本</button>;
    return <button type="button" onClick={() => setPending({ kind: "regression-bad-case", id })}><Bug size={15} />失败样本</button>;
  }

  if (data.isError) return <DataState kind="error" title="质量数据暂不可用" description="请确认 Agent API 基线与当前 base URL 后重试。" />;

  return (
    <main className="quality-workspace">
      <header className="quality-hero">
        <div>
          <p>设置 / 质量与高级</p>
          <h1>{copy.title}</h1>
          <span>{copy.description}</span>
        </div>
        <aside>
          <ShieldCheck size={18} aria-hidden="true" />
          <span>Shadow only</span>
          <strong>证据可读，策略不激活</strong>
          <p>Replay、Bad Case、Regression 与 Evaluation 都保留确认路径，不提供 active policy 控制。</p>
        </aside>
      </header>

      {data.partial ? <p className="quality-partial">部分质量证据仍在读取或暂不可用；已返回的数据会先展示，写操作仍需要确认。</p> : null}
      {actionError ? <p className="quality-error" role="alert">{actionError}</p> : null}

      <div className="quality-layout">
        <section className="quality-list" aria-label={`${copy.label} 列表`}>
          <div className="quality-list-heading"><Icon size={18} /><h2>{copy.label}</h2><span>{data.pagination?.total ?? data.items.length} 条</span></div>
          {data.isLoading ? <DataState kind="loading" title="正在读取质量证据" /> : data.items.length ? <div className="quality-rows">{data.items.map((item) => {
            const id = idOf(item);
            const active = selected && id && id === idOf(selected);
            return <button key={id || titleOf(item)} type="button" className={active ? "is-selected" : ""} onClick={() => { setSelectedId(id); if (view === "evaluation" || view === "regression") setResultPage(1); }}><span><strong>{titleOf(item)}</strong><small>{timeOf(item)}</small><em>{summaryOf(view, item)}</em></span><i>{statusOf(item)}</i></button>;
          })}</div> : <DataState kind="empty" title={copy.empty} description="当真实运行、回放、失败样本或评测结果产生后，会在这里显示。" />}
          <Pagination pagination={data.pagination} page={page} onPageChange={(nextPage) => { setSelectedId(null); setResultPage(1); setPage(nextPage); }} disabled={data.isLoading} />
        </section>

        <aside className="quality-inspector" aria-live="polite">
          {selected ? <>
            <small>Evidence Inspector</small>
            <h2>{titleOf(selected)}</h2>
            <p>{summaryOf(view, selected)}</p>
            <dl>
              <div><dt>状态</dt><dd>{statusOf(selected)}</dd></div>
              <div><dt>Trace</dt><dd>{text(selected, ["trace_run_id"], view === "trace" ? idOf(selected) || "—" : "—")}</dd></div>
              <div><dt>Replay</dt><dd>{text(selected, ["replay_id", "source_replay_id"], "—")}</dd></div>
              <div><dt>时间</dt><dd>{timeOf(selected)}</dd></div>
            </dl>
            {view === "evaluation" || view === "regression" ? <div className="quality-result-list">
              <small>本次运行结果</small>
              {resultQuery.isLoading ? <p>正在读取关联结果…</p> : resultQuery.data?.items.length ? resultQuery.data.items.map((result) => <div key={idOf(result)}><span><strong>{titleOf(result)}</strong><em>{statusOf(result)}</em></span><p>{summaryOf(view, result)}</p><div className="quality-inspector-actions">{actionsFor(result)}</div></div>) : <p>当前运行暂无结果记录。</p>}
              <Pagination pagination={resultQuery.data?.pagination} page={resultPage} onPageChange={setResultPage} disabled={resultQuery.isLoading} />
            </div> : <div className="quality-inspector-actions">{actionsFor(selected)}</div>}
            <pre>{JSON.stringify(selected, null, 2)}</pre>
          </> : <div className="quality-empty-inspector"><CheckCircle2 size={20} /><h2>选择一条证据</h2><p>这里会显示来源、状态、Trace/Replay 关联与可执行的确认动作。</p></div>}
        </aside>
      </div>

      {pending ? <ConfirmActionDialog {...actionCopy(pending)} confirmLabel={actionCopy(pending).label} cancelLabel="暂不处理" busy={saving} onConfirm={confirmAction} onCancel={() => setPending(null)} /> : null}
    </main>
  );
}
