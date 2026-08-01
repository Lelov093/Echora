"use client";

import { useState } from "react";
import { FlaskConical, Plus, RefreshCw } from "lucide-react";
import { createEvaluationDataset, createEvaluationRun } from "@/lib/api/evaluation";
import { createRegressionCase } from "@/lib/api/regression";
import { useEvaluationLab, useRegressionLab } from "@/lib/hooks/useQualityData";

export function EvaluationLab() {
  const evaluation = useEvaluationLab(30);
  const regression = useRegressionLab(30);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reloadAll() {
    await Promise.all([
      evaluation.datasets.reload(),
      evaluation.runs.reload(),
      evaluation.results.reload(),
      regression.cases.reload(),
      regression.runs.reload(),
      regression.results.reload(),
    ]);
  }

  async function act(label: string, action: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    try {
      await action();
      await reloadAll();
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
          <div className="agent-lab-eyebrow">Evaluation Lab</div>
          <h1>Checks and regressions</h1>
          <p>{evaluation.datasets.items.length} datasets / {regression.cases.items.length} regression cases</p>
        </div>
        <div className="agent-lab-actions">
          <button type="button" className="tool-icon-btn" aria-label="Refresh evaluation" onClick={reloadAll}>
            <RefreshCw size={17} />
          </button>
          <button type="button" className="glass-btn-secondary agent-lab-action" disabled={busy !== null} onClick={() => act("dataset", () => createEvaluationDataset({ name: "UI smoke dataset", dataset_type: "manual" }))}>
            <Plus size={16} /> Dataset
          </button>
          <button type="button" className="glass-btn-primary agent-lab-action" disabled={busy !== null} onClick={() => act("regression", () => createRegressionCase({ title: "UI regression case", case_type: "manual", expected_behavior: "Maintain current behavior." }))}>
            <FlaskConical size={16} /> Regression
          </button>
        </div>
      </section>

      {error && <div className="tool-error glass-soft">{error}</div>}

      <div className="agent-lab-grid agent-lab-grid-3">
        <section className="agent-lab-panel glass-soft">
          <div className="agent-lab-panel-head"><h2>Datasets</h2><span>{evaluation.datasets.items.length}</span></div>
          <div className="agent-lab-list">
            {evaluation.datasets.items.map((dataset) => (
              <article key={dataset.id} className="agent-lab-row">
                <div><strong>{dataset.name}</strong><span>{dataset.dataset_type} / {dataset.status}</span></div>
              </article>
            ))}
            {evaluation.datasets.items.length === 0 && <div className="tool-empty">No datasets yet.</div>}
          </div>
        </section>

        <section className="agent-lab-panel glass-soft">
          <div className="agent-lab-panel-head"><h2>Evaluation Runs</h2><span>{evaluation.runs.items.length}</span></div>
          <div className="agent-lab-list">
            {evaluation.runs.items.map((run) => (
              <article key={run.id} className="agent-lab-row">
                <div><strong>{run.status}</strong><span>{run.judge_type} / score {run.aggregate_score ?? "-"}</span></div>
              </article>
            ))}
            {evaluation.runs.items.length === 0 && (
              <button type="button" className="tool-empty" onClick={() => act("run", () => createEvaluationRun({ status: "completed", judge_type: "manual" }))}>
                Create manual run
              </button>
            )}
          </div>
        </section>

        <section className="agent-lab-panel glass-soft">
          <div className="agent-lab-panel-head"><h2>Regression Cases</h2><span>{regression.cases.items.length}</span></div>
          <div className="agent-lab-list">
            {regression.cases.items.map((item) => (
              <article key={item.id} className="agent-lab-row">
                <div><strong>{item.title}</strong><span>{item.case_type} / {item.status}</span><p>{item.expected_behavior}</p></div>
              </article>
            ))}
            {regression.cases.items.length === 0 && <div className="tool-empty">No regression cases yet.</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
