"use client";

import { useState } from "react";
import { CheckCircle2, LoaderCircle, ShieldCheck } from "lucide-react";
import { DataState } from "./DataState";
import { StatusMessage } from "./StatusMessage";
import { ConfirmActionDialog } from "./ConfirmActionDialog";

export function ComponentShowcase() {
  const [message, setMessage] = useState("Component states are ready for keyboard review.");
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <section className="orbital-component-showcase" aria-labelledby="orbital-component-showcase-title">
      <header>
        <div>
        <span>UI foundation</span>
          <h2 id="orbital-component-showcase-title">Component accessibility catalog</h2>
          <p>Interactive reference states for focus, status, forms, boundaries, and data feedback.</p>
        </div>
        <span className="orbital-component-boundary"><ShieldCheck size={15} /> No policy mutation</span>
      </header>

      <div className="orbital-component-showcase-grid">
        <div className="orbital-component-sample">
          <h3>Actions and live status</h3>
          <div className="orbital-component-actions">
            <button type="button" className="orbital-domain-primary" onClick={() => setMessage("Primary action announced successfully.")}>
              <CheckCircle2 size={15} /> Announce success
            </button>
            <button type="button" className="orbital-domain-secondary" onClick={() => setMessage("Secondary action announced successfully.")}>
              Secondary action
            </button>
            <button type="button" className="orbital-domain-secondary" disabled>
              <LoaderCircle size={15} /> Disabled
            </button>
            <button type="button" className="orbital-domain-secondary" onClick={() => setConfirmOpen(true)}>
              Preview destructive dialog
            </button>
          </div>
          <StatusMessage tone="success">{message}</StatusMessage>
        </div>

        <div className="orbital-component-sample">
          <h3>Persistent labels</h3>
          <div className="orbital-component-form">
            <label>
              <span>Companion scope</span>
              <input defaultValue="All Companions" readOnly />
            </label>
            <label>
              <span>Review state</span>
              <select defaultValue="pending">
                <option value="pending">Pending review</option>
                <option value="approved">Approved</option>
              </select>
            </label>
          </div>
        </div>
      </div>

      <DataState
        kind="partial"
        title="Partial data state"
        description="Loaded regions remain available while failed regions expose an independent retry action."
        action={<button type="button" className="orbital-domain-secondary" onClick={() => setMessage("Partial data retry requested.")}>Retry failed region</button>}
      />

      {confirmOpen ? (
        <ConfirmActionDialog
          title="Preview destructive action?"
          description="This catalog preview does not change data. It exists to verify focus trapping, Escape handling, and destructive-action hierarchy."
          confirmLabel="Confirm preview"
          onCancel={() => setConfirmOpen(false)}
          onConfirm={() => {
            setConfirmOpen(false);
            setMessage("Destructive dialog preview confirmed without changing data.");
          }}
        />
      ) : null}
    </section>
  );
}
