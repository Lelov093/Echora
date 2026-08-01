"use client";

import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, BookOpenText, Clock3, Download, FileText, LockKeyhole, Pencil, Plus, RefreshCcw, RotateCcw, Sparkles, Trash2, Undo2 } from "lucide-react";
import {
  archiveMemory, correctContextDocument, correctMemory, createMemory, deleteMemory, fadeMemory, invalidateContextDocument,
  listContextDocuments, listMemories, listMemoryRevisions, lockMemory, reactivateMemory,
  refreshContextDocuments, restoreContextDocument, restoreMemoryRevision,
  type ContextDocument, type MemoryItem, type MemoryRevision,
} from "@/lib/api/memories";
import { listConversations } from "@/lib/api/conversations";
import { useCompanionRosterQuery } from "@/lib/queries/companions";
import { DataState } from "@/components/patterns/DataState";
import { MemoryPolicySettings } from "@/components/memory/MemoryPolicySettings";
import { MemoryImpactPanel } from "@/components/memory/MemoryImpactPanel";

type MemoryAction = "lock" | "fade" | "archive" | "reactivate" | "correct" | "forget";

export function MemoryGovernance({ scopedCompanionId }: { scopedCompanionId?: string } = {}) {
  const searchParams = useSearchParams();
  const companionId = scopedCompanionId || searchParams.get("companion_id") || "";
  const client = useQueryClient();
  const roster = useCompanionRosterQuery();
  const conversations = useQuery({ queryKey: ["conversations", companionId], queryFn: () => listConversations({ companion_id: companionId, page_size: 8 }), enabled: Boolean(companionId) });
  const memories = useQuery({ queryKey: ["memory-governance", companionId], queryFn: () => listMemories({ companion_id: companionId, page_size: "100" }) as Promise<{ items: MemoryItem[] }>, enabled: Boolean(companionId) });
  const documents = useQuery({ queryKey: ["context-documents", companionId], queryFn: () => listContextDocuments(companionId, true), enabled: Boolean(companionId) });
  const [pending, setPending] = useState<MemoryItem | null>(null);
  const [action, setAction] = useState<MemoryAction | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [content, setContent] = useState("");
  const [historyMemory, setHistoryMemory] = useState<MemoryItem | null>(null);
  const [editingDocument, setEditingDocument] = useState<ContextDocument | null>(null);
  const [documentContent, setDocumentContent] = useState("");
  const [creating, setCreating] = useState(false);
  const [newMemory, setNewMemory] = useState({ content: "", type: "fact", importance: "0.6" });
  const [impactMemory, setImpactMemory] = useState<MemoryItem | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const revisions = useQuery({ queryKey: ["memory-revisions", historyMemory?.id, companionId], queryFn: () => listMemoryRevisions(historyMemory!.id, companionId), enabled: Boolean(historyMemory) });
  const modalOpen = creating || Boolean(editingDocument) || Boolean(pending && action);

  useEffect(() => {
    if (!modalOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
      const target = returnFocusRef.current;
      returnFocusRef.current = null;
      queueMicrotask(() => target?.focus());
    };
  }, [modalOpen]);

  const refreshAll = () => Promise.all([
    client.invalidateQueries({ queryKey: ["memory-governance", companionId] }),
    client.invalidateQueries({ queryKey: ["context-documents", companionId] }),
  ]);
  const mutate = useMutation({
    mutationFn: async () => {
      if (!pending || !action) return;
      if (action === "lock") return lockMemory(pending.id, companionId);
      if (action === "archive") return archiveMemory(pending.id, companionId);
      if (action === "reactivate") return reactivateMemory(pending.id, companionId);
      if (action === "fade") return fadeMemory(pending.id, companionId, { strength_delta: 0.2 });
      if (action === "correct") return correctMemory(pending.id, companionId, { content: content.trim(), summary: pending.summary, reason: "用户在伙伴记忆设置中更正内容", expected_revision: pending.content_revision });
      return deleteMemory(pending.id, companionId);
    },
    onSuccess: async () => { await refreshAll(); setPending(null); setAction(null); setConfirmed(false); setContent(""); },
  });
  const restoreRevision = useMutation({
    mutationFn: (revision: MemoryRevision) => restoreMemoryRevision(historyMemory!.id, revision.id, companionId, { expected_revision: historyMemory!.content_revision, reason: `用户恢复至修订 ${revision.revision}` }),
    onSuccess: async () => { await refreshAll(); await client.invalidateQueries({ queryKey: ["memory-revisions", historyMemory?.id, companionId] }); setHistoryMemory(null); },
  });
  const refreshDocuments = useMutation({
    mutationFn: () => {
      const conversation = conversations.data?.items[0];
      const userId = roster.data?.items.find((item) => item.id === companionId)?.user_id;
      if (!conversation || !userId) throw new Error("需要一段标准对话作为证据来源");
      return refreshContextDocuments(companionId, { user_id: userId, conversation_id: conversation.id, force: true });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["context-documents", companionId] }),
  });
  const saveDocument = useMutation({
    mutationFn: () => correctContextDocument(companionId, editingDocument!.id, { expected_version: editingDocument!.version, content: documentContent.trim(), reason: "用户更正上下文文档" }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ["context-documents", companionId] }); setEditingDocument(null); },
  });
  const documentAction = useMutation({
    mutationFn: ({ document, operation }: { document: ContextDocument; operation: "restore" | "invalidate" }) => operation === "restore"
      ? restoreContextDocument(companionId, document.id, { expected_version: activeVersion(documents.data?.items, document.document_kind), reason: `用户恢复版本 ${document.version}` })
      : invalidateContextDocument(companionId, document.id, { expected_version: document.version, reason: "用户停用当前上下文文档" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["context-documents", companionId] }),
  });
  const create = useMutation({
    mutationFn: () => {
      const userId = roster.data?.items.find((item) => item.id === companionId)?.user_id;
      if (!userId) throw new Error("无法确认当前伙伴的用户范围");
      return createMemory({
        user_id: userId,
        companion_id: companionId,
        content: newMemory.content.trim(),
        type: newMemory.type,
        importance: Number(newMemory.importance),
        confidence: 1,
      });
    },
    onSuccess: async () => {
      await refreshAll();
      setCreating(false);
      setNewMemory({ content: "", type: "fact", importance: "0.6" });
    },
  });
  const exportAll = useMutation({
    mutationFn: async () => {
      const exported: MemoryItem[] = [];
      let page = 1;
      let totalPages = 1;
      do {
        const result = await listMemories({
          companion_id: companionId,
          page: String(page),
          page_size: "100",
        }) as { items: MemoryItem[]; pagination: { total_pages: number } };
        exported.push(...result.items);
        totalPages = result.pagination.total_pages;
        page += 1;
      } while (page <= totalPages);
      return exported;
    },
    onSuccess: (exported) => {
      const blob = new Blob([JSON.stringify({
        schema: "echora.companion-memories.v1",
        exported_at: new Date().toISOString(),
        companion_id: companionId,
        memories: exported,
      }, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `echora-memories-${companionId}.json`;
      link.click();
      URL.revokeObjectURL(url);
    },
  });

  function rememberReturnFocus() {
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }
  function begin(memory: MemoryItem, next: MemoryAction) { rememberReturnFocus(); setPending(memory); setAction(next); setConfirmed(false); setContent(memory.content); }
  if (!companionId) return <DataState kind="empty" title="请选择一位伙伴" description="记忆始终在单一伙伴范围内操作。" />;
  if (memories.isLoading) return <DataState kind="loading" title="正在读取伙伴记忆" />;
  if (memories.isError || !memories.data) return <DataState kind="error" title="暂时无法读取伙伴记忆" />;
  const rows = memories.data.items;
  const activeDocuments = (documents.data?.items ?? []).filter((item) => item.status === "active");
  const historyDocuments = (documents.data?.items ?? []).filter((item) => item.status !== "active");
  const actionLabel: Record<MemoryAction, string> = { lock: "锁定记忆", fade: "淡化影响", archive: "归档记忆", reactivate: "恢复记忆", correct: "更正记忆", forget: "忘记记忆" };

  return <section className="memory-governance">
    <header><span>设置 / 伙伴记忆</span><span>Companion 私有 · 版本化</span></header>
    <div className="memory-governance-hero"><div><span>可检查、可更正、可撤回</span><h1>让记忆保持可信，<br />也保留改变的余地。</h1></div><p>每次更正、合并和恢复都会形成不可变历史，并在真实向量重建成功后原子提交。跨伙伴、共享与频道内容仍由原有审核边界保护。</p></div>

    <MemoryPolicySettings companionId={companionId} />

    <section className="memory-owner-toolbar" aria-label="记忆操作">
      <div><small>由你直接决定</small><h2>补充伙伴应该记住的事</h2><p>手动补充会作为当前伙伴的私有、已确认记忆保存，并立即建立真实向量索引。</p></div>
      <div><button type="button" onClick={() => { rememberReturnFocus(); setCreating(true); }}><Plus size={16} />补充一条记忆</button><button type="button" onClick={() => exportAll.mutate()} disabled={!rows.length || exportAll.isPending}><Download size={16} />{exportAll.isPending ? "正在整理全部记忆…" : "导出全部记忆"}</button></div>
    </section>
    {exportAll.isError ? <p className="memory-export-error" role="alert">导出过程中有页面读取失败，请检查连接后重试。</p> : null}

    <section className="context-document-section">
      <header><div><small>动态上下文</small><h2>近期摘要与长期档案</h2><p>由真实 Provider 从当前伙伴的有界证据生成；可人工更正、停用和恢复历史版本。</p></div><button type="button" onClick={() => refreshDocuments.mutate()} disabled={refreshDocuments.isPending || !conversations.data?.items.length}><RefreshCcw size={16} />{refreshDocuments.isPending ? "生成中" : "重新生成"}</button></header>
      {refreshDocuments.isError ? <p role="alert">未能生成上下文文档；请确认存在标准对话且 Provider 可用。</p> : null}
      <div className="context-document-grid">{activeDocuments.length ? activeDocuments.map((document) => <article key={document.id}>
        <FileText size={19} /><div><small>{document.document_kind === "recent_summary" ? "近期摘要" : "长期档案"} · v{document.version}</small><p>{document.content}</p><span>置信度 {Math.round(document.confidence * 100)}% · {document.source_message_ids.length} 条消息证据 · {document.source_memory_ids.length} 条记忆证据</span></div>
        <div><button type="button" onClick={() => { rememberReturnFocus(); setEditingDocument(document); setDocumentContent(document.content); }}><Pencil size={15} />更正</button><button type="button" onClick={() => documentAction.mutate({ document, operation: "invalidate" })}><Archive size={15} />停用</button></div>
      </article>) : <DataState kind="empty" title="尚未形成上下文文档" description="完成至少两轮有证据的标准对话后，可在这里生成。" />}</div>
      {historyDocuments.length ? <details className="context-document-history"><summary>查看历史版本（{historyDocuments.length}）</summary>{historyDocuments.map((document) => <div key={document.id}><span>{document.document_kind} · v{document.version} · {document.status}</span><p>{document.content}</p><button type="button" onClick={() => documentAction.mutate({ document, operation: "restore" })}><Undo2 size={14} />恢复为新版本</button></div>)}</details> : null}
    </section>

    <div className="memory-governance-list">{rows.length ? rows.map((memory) => <article key={memory.id}>
      <BookOpenText size={18} /><div><small>{memoryStateLabel(memory.state)} · {memoryTypeLabel(memory.type)} · 修订 {memory.content_revision}</small><h2>{memory.summary || memory.content}</h2><p>{memory.content}</p><span>当前影响 {memoryStrengthLabel(memory.memory_strength)} · 可信程度 {confidenceLabel(memory.confidence)}</span></div>
      <div className="memory-actions"><button type="button" onClick={() => setImpactMemory(memory)}><Sparkles size={15} />如何影响相处</button><button type="button" onClick={() => setHistoryMemory(memory)}><Clock3 size={15} />历史</button>{memory.state !== "archived" ? <button type="button" onClick={() => begin(memory, "correct")}><Pencil size={15} />更正</button> : null}{!["archived", "locked"].includes(memory.state) ? <button type="button" onClick={() => begin(memory, "lock")}><LockKeyhole size={15} />锁定</button> : null}{!["archived", "dormant"].includes(memory.state) ? <button type="button" onClick={() => begin(memory, "fade")}><Sparkles size={15} />淡化</button> : null}{["archived", "dormant"].includes(memory.state) ? <button type="button" onClick={() => begin(memory, "reactivate")}><RotateCcw size={15} />恢复</button> : <button type="button" onClick={() => begin(memory, "archive")}><Archive size={15} />归档</button>}<button type="button" onClick={() => begin(memory, "forget")}><Trash2 size={15} />忘记</button></div>
    </article>) : <DataState kind="empty" title="暂时没有长期记忆" description="当你确认值得长期保留的内容后，它会在这里出现。" />}</div>

    {impactMemory ? <section className="memory-history-panel memory-impact-panel-drawer"><header><div><small>这条记忆如何参与相处</small><h2>{impactMemory.summary || impactMemory.content}</h2></div><button type="button" onClick={() => setImpactMemory(null)}>关闭</button></header><MemoryImpactPanel memoryId={impactMemory.id} /></section> : null}
    {historyMemory ? <section className="memory-history-panel"><header><div><small>不可变修订历史</small><h2>{historyMemory.summary || "伙伴记忆"}</h2></div><button type="button" onClick={() => setHistoryMemory(null)}>关闭</button></header>{revisions.isLoading ? <DataState kind="loading" title="正在读取历史" /> : revisions.data?.items.map((revision) => <article key={revision.id}><div><b>修订 {revision.revision}</b><span>{revision.operation} · {new Date(revision.created_at).toLocaleString("zh-CN")}</span></div><p>{revision.content}</p>{revision.revision !== historyMemory.content_revision ? <button type="button" onClick={() => restoreRevision.mutate(revision)} disabled={restoreRevision.isPending}><Undo2 size={14} />恢复为新修订</button> : <em>当前内容</em>}</article>)}</section> : null}
    {creating ? <section className="memory-confirm memory-create-panel is-editor" role="dialog" aria-modal="true" aria-labelledby="memory-create-title" onKeyDown={trapDialogFocus}><div><small>补充私有记忆</small><h2 id="memory-create-title">你希望伙伴以后记得什么？</h2><p>这条内容会在真实向量索引建立成功后进入当前伙伴的长期记忆。</p><textarea autoFocus value={newMemory.content} onChange={(event) => setNewMemory({ ...newMemory, content: event.target.value })} maxLength={100000} aria-label="新记忆内容" /><div className="memory-create-options"><label><span>记忆类型</span><select value={newMemory.type} onChange={(event) => setNewMemory({ ...newMemory, type: event.target.value })}><option value="fact">事实</option><option value="preference">偏好</option><option value="goal">长期目标</option><option value="relationship">关系约定</option><option value="correction">重要纠正</option><option value="episodic">共同经历</option></select></label><label><span>希望影响程度</span><select value={newMemory.importance} onChange={(event) => setNewMemory({ ...newMemory, importance: event.target.value })}><option value="0.35">轻微参考</option><option value="0.6">自然记住</option><option value="0.85">重要记忆</option></select></label></div><footer><button type="button" disabled={!newMemory.content.trim() || create.isPending} onClick={() => create.mutate()}>{create.isPending ? "正在保存与建立索引…" : "保存为伙伴记忆"}</button><button type="button" disabled={create.isPending} onClick={() => setCreating(false)}>取消</button></footer>{create.isError ? <p role="alert">保存失败；请确认 Embedding 与数据库连接后重试，输入内容仍会保留。</p> : null}</div></section> : null}
    {editingDocument ? <section className="memory-confirm is-editor" role="dialog" aria-modal="true" aria-labelledby="memory-document-edit-title" onKeyDown={trapDialogFocus}><div><small>更正上下文文档 v{editingDocument.version}</small><h2 id="memory-document-edit-title">修正伙伴当前使用的上下文</h2><textarea autoFocus value={documentContent} onChange={(event) => setDocumentContent(event.target.value)} aria-label="更正后的上下文文档" /><footer><button type="button" disabled={!documentContent.trim() || saveDocument.isPending} onClick={() => saveDocument.mutate()}>保存为新版本</button><button type="button" onClick={() => setEditingDocument(null)}>取消</button></footer>{saveDocument.isError ? <p role="alert">版本可能已变化，请刷新后重试；当前输入仍会保留。</p> : null}</div></section> : null}
    {pending && action ? <section className={`memory-confirm ${action === "correct" ? "is-editor" : "is-compact"}`} role="dialog" aria-modal="true" aria-labelledby="memory-action-title" onKeyDown={trapDialogFocus}><div><small>{actionLabel[action]} · 当前修订 {pending.content_revision}</small><h2 id="memory-action-title">{pending.summary || "这条伙伴记忆"}</h2>{action === "correct" ? <textarea autoFocus value={content} onChange={(event) => setContent(event.target.value)} aria-label="更正后的记忆内容" /> : <p>{action === "forget" ? "忘记会移除长期召回内容，同时保留必要生命周期证据。" : action === "fade" ? "淡化会降低它参与未来回复、成长和 Presence 的机会；之后仍可重新激活。" : "操作只影响当前伙伴的私有记忆；内容版本发生冲突时不会覆盖新数据。"}</p>}<label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />我理解这会影响当前伙伴的私有记忆。</label><footer><button type="button" disabled={!confirmed || mutate.isPending || (action === "correct" && !content.trim())} onClick={() => mutate.mutate()}>{mutate.isPending ? "正在保存" : `确认${actionLabel[action]}`}</button><button type="button" onClick={() => { setPending(null); setAction(null); }}>取消</button></footer>{mutate.isError ? <p role="alert">内容可能已被其他操作更新，请刷新后重试；当前输入仍会保留。</p> : null}</div></section> : null}
  </section>;
}

function activeVersion(items: ContextDocument[] | undefined, kind: ContextDocument["document_kind"]) {
  return items?.find((item) => item.document_kind === kind && item.status === "active")?.version ?? 0;
}

function trapDialogFocus(event: ReactKeyboardEvent<HTMLElement>) {
  if (event.key !== "Tab") return;
  const focusable = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
    "button:not([disabled]), textarea:not([disabled]), select:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex='-1'])",
  ));
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function memoryStateLabel(value: string) {
  return ({ active: "正在使用", locked: "已锁定", dormant: "已淡化", archived: "已归档", consolidated: "已整合" } as Record<string, string>)[value] ?? "已保存";
}
function memoryTypeLabel(value: string) {
  return ({ fact: "事实", preference: "偏好", goal: "长期目标", relationship: "关系", correction: "纠正", episodic: "共同经历", emotional: "情绪线索", project: "项目" } as Record<string, string>)[value] ?? "长期记忆";
}
function memoryStrengthLabel(value: number) { return value >= 0.75 ? "重要" : value >= 0.45 ? "自然参与" : "轻微参考"; }
function confidenceLabel(value: number) { return value >= 0.8 ? "较高" : value >= 0.55 ? "中等" : "待核对"; }
