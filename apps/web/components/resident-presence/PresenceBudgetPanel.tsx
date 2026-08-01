"use client";

import { Gauge } from "lucide-react";
import type { PresenceBudgetEvaluation } from "@/lib/types";

export function PresenceBudgetPanel({
  budget,
  onEvaluate,
  saving,
}: {
  budget: PresenceBudgetEvaluation | null;
  onEvaluate?: () => Promise<unknown>;
  saving?: boolean;
}) {
  const usedMinutes = budget?.used_presence_minutes ?? 0;
  const maxMinutes = budget?.max_presence_minutes ?? 0;
  const minuteRatio = maxMinutes > 0 ? Math.min(100, Math.round((usedMinutes / maxMinutes) * 100)) : 0;

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Gauge size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Presence Budget</h2>
          <p>Interruption limits and quiet-presence budget enforcement.</p>
        </div>
      </div>

      <button className="act-btn" onClick={onEvaluate} disabled={!onEvaluate || saving}>Evaluate budget</button>

      {!budget ? (
        <div className="domain-inline-empty">No budget evaluation has been run.</div>
      ) : (
        <div className="domain-list">
          <div className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <strong>{budget.decision}</strong>
              <span className="pill-sm">allowed {String(budget.allowed)}</span>
            </div>
            <div className="domain-list-sub">{budget.budget_scope} · {budget.enforcement_policy}</div>
            <div className="domain-detail-label">Presence minutes {usedMinutes}/{maxMinutes}</div>
            <div style={{ height: 8, borderRadius: 999, background: "rgba(120,150,190,0.18)", overflow: "hidden" }}>
              <div style={{ width: `${minuteRatio}%`, height: "100%", background: "rgba(53,179,139,0.55)" }} />
            </div>
          </div>
          <pre className="domain-code-block">{JSON.stringify(budget.budget_policy_json, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}
