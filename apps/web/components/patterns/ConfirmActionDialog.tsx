"use client";

import { useId, useRef } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useModalDialog } from "@/lib/hooks/useModalDialog";

export function ConfirmActionDialog({
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  busy = false,
  onConfirm,
  onCancel,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  useModalDialog({ dialogRef, initialFocusRef: cancelRef, onClose: onCancel });

  return (
    <div className="orbital-confirm-overlay" onClick={busy ? undefined : onCancel}>
      <div
        ref={dialogRef}
        className="orbital-confirm-dialog"
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
          <h2 id={titleId}>{title}</h2>
          <p id={descriptionId}>{description}</p>
        </div>
        <div className="orbital-confirm-actions">
          <Button ref={cancelRef} type="button" variant="outline" disabled={busy} onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button type="button" variant="destructive" disabled={busy} onClick={() => void onConfirm()}>
            {busy ? "Working..." : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
