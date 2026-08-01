"use client";

import { createPortal } from "react-dom";
import { useId, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ConversationDeletionPreview } from "@/lib/api/conversations";
import { useModalDialog } from "@/lib/hooks/useModalDialog";

export function ConversationDeletionDialog({
  ...props
}: ConversationDeletionDialogProps) {
  if (typeof document === "undefined") return null;
  return createPortal(
    <ConversationDeletionDialogContent {...props} />,
    document.body,
  );
}

type ConversationDeletionDialogProps = {
  preview: ConversationDeletionPreview;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
};

function ConversationDeletionDialogContent({
  preview,
  busy,
  error,
  onCancel,
  onConfirm,
}: ConversationDeletionDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const [phrase, setPhrase] = useState("");
  const [understood, setUnderstood] = useState(false);
  useModalDialog({
    dialogRef,
    initialFocusRef: cancelRef,
    onClose: busy ? () => undefined : onCancel,
  });

  const canSubmit = phrase === preview.requires_phrase && understood && !busy;
  const visibleCounts = Object.entries(preview.affected_counts)
    .filter(([key, value]) => key !== "related_records" && value > 0);

  return (
    <div className="orbital-confirm-overlay" onClick={busy ? undefined : onCancel}>
      <div
        ref={dialogRef}
        className="orbital-confirm-dialog conversation-deletion-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="orbital-confirm-icon" aria-hidden="true">
          <AlertTriangle size={20} />
        </div>
        <div>
          <small>永久删除已归档对话</small>
          <h2 id={titleId}>删除“{preview.title || "未命名对话"}”？</h2>
          <p id={descriptionId}>
            对话正文、由本对话形成的记忆与成长理解、工具和任务活动会被永久删除。
            已独立存在的共同空间、项目任务与主动陪伴计划不会被连带删除，但会解除对这段对话的引用。
          </p>
        </div>

        {visibleCounts.length ? (
          <div className="conversation-deletion-scope" aria-label="将永久删除的内容">
            {visibleCounts.map(([key, count]) => (
              <span key={key}>
                <strong>{countLabels[key] ?? key}</strong>
                {count}
              </span>
            ))}
          </div>
        ) : null}

        {preview.affected_counts.channel_bindings > 0 ? (
          <p className="conversation-deletion-warning">
            这段对话仍关联渠道会话。删除后，相应渠道需要重新建立新的对话连续性。
          </p>
        ) : null}

        <label className="companion-deletion-name">
          <span>
            输入 <strong>{preview.requires_phrase}</strong> 以确认
          </span>
          <input
            autoFocus
            value={phrase}
            disabled={busy}
            onChange={(event) => setPhrase(event.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
        </label>

        <label className="companion-deletion-understanding">
          <input
            type="checkbox"
            checked={understood}
            disabled={busy}
            onChange={(event) => setUnderstood(event.target.checked)}
          />
          <span>我理解这次删除不能恢复，且这段对话形成的私有记忆也会一并移除。</span>
        </label>

        {error ? <p className="companion-deletion-error" role="alert">{error}</p> : null}

        <div className="orbital-confirm-actions">
          <Button
            ref={cancelRef}
            type="button"
            variant="outline"
            disabled={busy}
            onClick={onCancel}
          >
            取消
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={!canSubmit}
            onClick={() => void onConfirm()}
          >
            {busy ? "正在删除…" : "永久删除对话"}
          </Button>
        </div>
      </div>
    </div>
  );
}

const countLabels: Record<string, string> = {
  messages: "消息",
  memories: "伙伴记忆",
  growth: "成长理解",
  tool_runs: "工具活动",
  task_runs: "任务活动",
  channel_bindings: "渠道绑定",
};
