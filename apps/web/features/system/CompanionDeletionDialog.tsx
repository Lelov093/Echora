"use client";

import { useId, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useModalDialog } from "@/lib/hooks/useModalDialog";

export type CompanionDeletionChoice = {
  confirmationName: string;
  skipRecoveryWindow: boolean;
};

export function CompanionDeletionDialog({
  companionName,
  affectedCounts,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  companionName: string;
  affectedCounts: Record<string, number>;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (choice: CompanionDeletionChoice) => void | Promise<void>;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const [confirmationName, setConfirmationName] = useState("");
  const [skipRecoveryWindow, setSkipRecoveryWindow] = useState(false);
  const [understood, setUnderstood] = useState(false);
  useModalDialog({
    dialogRef,
    initialFocusRef: cancelRef,
    onClose: busy ? () => undefined : onCancel,
  });

  const nameMatches =
    confirmationName.trim().toLocaleLowerCase() ===
    companionName.trim().toLocaleLowerCase();
  const canSubmit = nameMatches && understood && !busy;

  return (
    <div
      className="orbital-confirm-overlay"
      onClick={busy ? undefined : onCancel}
    >
      <div
        ref={dialogRef}
        className="orbital-confirm-dialog companion-deletion-dialog"
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
          <small>删除伙伴与共同数据</small>
          <h2 id={titleId}>确认删除“{companionName}”？</h2>
          <p id={descriptionId}>
            删除会先停止这位伙伴的渠道、主动陪伴和未完成任务。默认进入
            30 天恢复期；你也可以明确选择立即永久删除。
          </p>
        </div>

        <div className="companion-deletion-scope" aria-label="预计影响范围">
          {Object.entries(affectedCounts).map(([key, count]) => (
            <span key={key}>
              <strong>{deletionCountLabels[key] ?? key}</strong>
              {count}
            </span>
          ))}
        </div>

        <fieldset className="companion-deletion-options">
          <legend>选择删除方式</legend>
          <label>
            <input
              type="radio"
              name="deletion-mode"
              checked={!skipRecoveryWindow}
              disabled={busy}
              onChange={() => setSkipRecoveryWindow(false)}
            />
            <span>
              <strong>移到回收区 30 天</strong>
              <small>期间可以恢复；到期后自动永久删除。</small>
            </span>
          </label>
          <label>
            <input
              type="radio"
              name="deletion-mode"
              checked={skipRecoveryWindow}
              disabled={busy}
              onChange={() => setSkipRecoveryWindow(true)}
            />
            <span>
              <strong>立即永久删除</strong>
              <small>跳过恢复期，执行开始后无法撤销。</small>
            </span>
          </label>
        </fieldset>

        <label className="companion-deletion-name">
          <span>
            输入伙伴名称 <strong>{companionName}</strong> 以确认
          </span>
          <input
            autoFocus
            value={confirmationName}
            disabled={busy}
            onChange={(event) => setConfirmationName(event.target.value)}
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
          <span>
            我已按需下载数据副本，或明确选择不导出，并理解删除不会自动创建副本。
          </span>
        </label>

        {error ? (
          <p className="companion-deletion-error" role="alert">
            {error}
          </p>
        ) : null}

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
            onClick={() =>
              void onConfirm({ confirmationName, skipRecoveryWindow })
            }
          >
            {busy
              ? "正在执行…"
              : skipRecoveryWindow
                ? "立即永久删除"
                : "移到回收区"}
          </Button>
        </div>
      </div>
    </div>
  );
}

const deletionCountLabels: Record<string, string> = {
  conversations: "对话",
  messages: "消息",
  private_memories: "伙伴记忆",
  channel_bindings: "渠道绑定",
  tool_runs: "工具运行",
};
