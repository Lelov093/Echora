"use client";

import { useState } from "react";
import { Bug, GitPullRequestCreate, RefreshCw } from "lucide-react";
import { convertInboxItemToRegressionCase, createBadCaseInboxItem, triageBadCaseInboxItem } from "@/lib/api/badCaseInbox";
import { useBadCaseInbox } from "@/lib/hooks/useQualityData";

export function BadCaseInboxPanel() {
  const inbox = useBadCaseInbox(undefined, 60);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(label: string, action: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    try {
      await action();
      await inbox.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="agent-lab-page">
      <section className="agent-lab-hero dynamic-glass">
        <div>
          <div className="agent-lab-eyebrow">Bad Case Inbox</div>
          <h1>Quality signals</h1>
          <p>{inbox.items.length} items / {inbox.items.filter((item) => item.status === "open").length} open</p>
        </div>
        <div className="agent-lab-actions">
          <button type="button" className="tool-icon-btn" aria-label="Refresh bad cases" onClick={inbox.reload}>
            <RefreshCw size={17} />
          </button>
          <button
            type="button"
            className="glass-btn-primary agent-lab-action"
            disabled={busy !== null}
            onClick={() => act("create", () => createBadCaseInboxItem({
              source_type: "manual",
              case_type: "ui_review",
              severity: "medium",
              title: "Manual review item",
              description: "Created from Bad Case Inbox",
            }))}
          >
            <Bug size={16} /> New item
          </button>
        </div>
      </section>

      {error && <div className="tool-error glass-soft">{error}</div>}

      <section className="agent-lab-panel glass-soft">
        <div className="agent-lab-panel-head"><h2>Inbox</h2><span>{inbox.loading ? "loading" : inbox.items.length}</span></div>
        <div className="agent-lab-list">
          {inbox.items.map((item) => (
            <article key={item.id} className="agent-lab-row bad-case-row">
              <div>
                <strong>{item.title}</strong>
                <span>{item.case_type} / {item.severity} / {item.status}</span>
                {item.description && <p>{item.description}</p>}
              </div>
              <div className="agent-lab-row-actions">
                <button type="button" aria-label="Triage item" onClick={() => act(`${item.id}-triage`, () => triageBadCaseInboxItem(item.id, { action: "triage", new_status: "triaged" }))}>
                  <Bug size={16} />
                </button>
                <button type="button" aria-label="Create regression case" onClick={() => act(`${item.id}-regression`, () => convertInboxItemToRegressionCase(item.id))}>
                  <GitPullRequestCreate size={16} />
                </button>
              </div>
            </article>
          ))}
          {!inbox.loading && inbox.items.length === 0 && <div className="tool-empty">No bad case items yet.</div>}
        </div>
      </section>
    </div>
  );
}
