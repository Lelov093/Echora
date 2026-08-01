"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Archive, Check, Ellipsis, Pencil, RotateCcw, Save, Trash2, X } from "lucide-react";
import {
  archiveConversation,
  correctMessage,
  permanentlyDeleteConversation,
  previewConversationDeletion,
  restoreConversation,
  updateConversation,
  withdrawMessage,
  type ConversationBrief,
  type ConversationDeletionPreview,
  type MessageBrief,
} from "@/lib/api/conversations";
import { ConversationDeletionDialog } from "@/features/conversation/ConversationDeletionDialog";

type Refresh = () => Promise<unknown>;

export function ConversationListItem({
  conversation,
  companionId,
  current,
  onChanged,
  onDeleted,
  onNavigate,
}: {
  conversation: ConversationBrief;
  companionId: string;
  current: boolean;
  onChanged: Refresh;
  onDeleted: Refresh;
  onNavigate?: () => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState(conversation.title ?? "");
  const [deletionPreview, setDeletionPreview] = useState<ConversationDeletionPreview | null>(null);
  const isArchived = conversation.status === "archived";
  const change = useMutation({
    mutationFn: async (kind: "rename" | "archive" | "restore") => {
      if (kind === "rename") return updateConversation(conversation.id, companionId, { title: title.trim() });
      return kind === "archive"
        ? archiveConversation(conversation.id, companionId)
        : restoreConversation(conversation.id, companionId);
    },
    onSuccess: async (_, kind) => {
      if (kind === "rename") setRenaming(false);
      await onChanged();
    },
  });
  const loadDeletionPreview = useMutation({
    mutationFn: () => previewConversationDeletion(conversation.id, companionId),
    onSuccess: setDeletionPreview,
  });
  const permanentDelete = useMutation({
    mutationFn: () => permanentlyDeleteConversation(conversation.id, companionId, "永久删除"),
    onSuccess: async () => {
      setDeletionPreview(null);
      await onDeleted();
    },
  });

  function submitRename(event: FormEvent) {
    event.preventDefault();
    if (title.trim() && !change.isPending) change.mutate("rename");
  }

  return (
    <div className="conversation-list-item" data-current={current || undefined}>
      {renaming ? (
        <form className="conversation-list-rename" onSubmit={submitRename}>
          <input value={title} onChange={(event) => setTitle(event.target.value)} aria-label="对话标题" autoFocus />
          <button type="submit" disabled={!title.trim() || change.isPending} aria-label="保存标题"><Check size={15} /></button>
          <button type="button" onClick={() => { setTitle(conversation.title ?? ""); setRenaming(false); }} disabled={change.isPending} aria-label="取消重命名"><X size={15} /></button>
        </form>
      ) : (
        <>
          <Link href={`/companions/${companionId}/conversations/${conversation.id}`} onClick={onNavigate} aria-current={current ? "page" : undefined}>
            <strong>{conversation.title || conversation.current_topic || "未命名对话"}</strong>
            {isArchived ? <small>已归档</small> : null}
          </Link>
          <div className="conversation-list-actions">
            {!isArchived ? <button type="button" onClick={() => { setTitle(conversation.title ?? ""); setRenaming(true); }} aria-label={`重命名 ${conversation.title || "未命名对话"}`}><Pencil size={15} /></button> : null}
            <details>
              <summary aria-label={`管理 ${conversation.title || "未命名对话"}`}><Ellipsis size={17} /></summary>
              <div className="conversation-list-menu">
                {!isArchived ? <button type="button" onClick={() => { setTitle(conversation.title ?? ""); setRenaming(true); }}><Pencil size={15} />重命名</button> : null}
                <button type="button" className={isArchived ? undefined : "is-danger"} onClick={() => change.mutate(isArchived ? "restore" : "archive")} disabled={change.isPending}>
                  {isArchived ? <RotateCcw size={15} /> : <Archive size={15} />}{isArchived ? "恢复对话" : "归档对话"}
                </button>
                {isArchived ? (
                  <button
                    type="button"
                    className="is-danger"
                    onClick={() => loadDeletionPreview.mutate()}
                    disabled={loadDeletionPreview.isPending}
                  >
                    <Trash2 size={15} />
                    {loadDeletionPreview.isPending ? "正在核对…" : "永久删除"}
                  </button>
                ) : null}
              </div>
            </details>
          </div>
        </>
      )}
      {change.isError || loadDeletionPreview.isError ? <p role="alert">操作未完成，请检查连接后重试。</p> : null}
      {deletionPreview ? (
        <ConversationDeletionDialog
          preview={deletionPreview}
          busy={permanentDelete.isPending}
          error={permanentDelete.error instanceof Error ? permanentDelete.error.message : null}
          onCancel={() => {
            if (!permanentDelete.isPending) {
              permanentDelete.reset();
              setDeletionPreview(null);
            }
          }}
          onConfirm={async () => {
            await permanentDelete.mutateAsync();
          }}
        />
      ) : null}
    </div>
  );
}

export function MessageLifecycleActions({
  message,
  conversationId,
  companionId,
  onChanged,
}: {
  message: MessageBrief;
  conversationId: string;
  companionId: string;
  onChanged: Refresh;
}) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(message.content);
  const [confirmWithdraw, setConfirmWithdraw] = useState(false);
  const mutation = useMutation({
    mutationFn: async (kind: "correct" | "withdraw") => {
      if (kind === "correct") {
        return correctMessage(conversationId, message.id, companionId, {
          content: content.trim(),
          reason: "用户在对话中更正原消息",
        });
      }
      return withdrawMessage(conversationId, message.id, companionId, "用户撤回原消息");
    },
    onSuccess: async () => {
      setEditing(false);
      setConfirmWithdraw(false);
      await onChanged();
    },
  });

  if (message.role !== "user") return null;
  return (
    <div className="message-lifecycle-actions">
      <div className="message-action-buttons">
        <button type="button" onClick={() => { setContent(message.content); setEditing(true); }} aria-label="更正这条消息"><Pencil size={15} /><span>更正</span></button>
        <button type="button" onClick={() => setConfirmWithdraw(true)} aria-label="撤回这条消息"><Trash2 size={15} /><span>撤回</span></button>
      </div>
      {editing ? (
        <form className="message-edit-panel" onSubmit={(event) => { event.preventDefault(); if (content.trim()) mutation.mutate("correct"); }}>
          <textarea value={content} onChange={(event) => setContent(event.target.value)} aria-label="更正消息内容" autoFocus />
          <div><button type="submit" disabled={mutation.isPending || !content.trim()}><Save size={14} />保存更正</button><button type="button" onClick={() => setEditing(false)} disabled={mutation.isPending}>取消</button></div>
          <small>更正会保留审计历史；当前版本不会自动重生成后续回复。</small>
        </form>
      ) : null}
      {confirmWithdraw ? (
        <div className="message-withdraw-panel" role="alertdialog" aria-label="确认撤回消息">
          <span>撤回后将从当前对话中隐藏。</span>
          <button type="button" onClick={() => mutation.mutate("withdraw")} disabled={mutation.isPending} className="is-danger"><Trash2 size={14} />确认撤回</button>
          <button type="button" onClick={() => setConfirmWithdraw(false)} disabled={mutation.isPending}>取消</button>
        </div>
      ) : null}
      {mutation.isError ? <p role="alert">操作未保存，请检查连接后重试。</p> : null}
    </div>
  );
}
