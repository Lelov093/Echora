"use client";

import { useState } from "react";
import { MessageSquarePlus, RefreshCw, RotateCcw } from "lucide-react";
import { createReplayAnnotation, createReplayBadCase, createReplayRegressionCase } from "@/lib/api/replays";
import { useReplays } from "@/lib/hooks/useQualityData";

export function ReplayCenter() {
  const replays = useReplays(undefined, 50);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selected = replays.items.find((replay) => replay.id === selectedId) || replays.items[0] || null;

  async function act(label: string, action: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    try {
      await action();
      await replays.reload();
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
          <div className="agent-lab-eyebrow">Replay Center</div>
          <h1>Run snapshots</h1>
          <p>{replays.items.length} replays / {selected?.status || "none"}</p>
        </div>
        <div className="agent-lab-actions">
          <button type="button" className="tool-icon-btn" aria-label="Refresh replays" onClick={replays.reload}>
            <RefreshCw size={17} />
          </button>
        </div>
      </section>

      {error && <div className="tool-error glass-soft">{error}</div>}

      <div className="agent-lab-grid">
        <section className="agent-lab-panel glass-soft">
          <div className="agent-lab-panel-head"><h2>Replays</h2><span>{replays.loading ? "loading" : replays.items.length}</span></div>
          <div className="agent-lab-list">
            {replays.items.map((replay) => (
              <button key={replay.id} type="button" className={`agent-lab-row agent-lab-button-row ${selected?.id === replay.id ? "agent-lab-row-active" : ""}`} onClick={() => setSelectedId(replay.id)}>
                <div>
                  <strong>{replay.title || replay.id.slice(0, 8)}</strong>
                  <span>{replay.replay_type} / {replay.status}</span>
                  {replay.summary && <p>{replay.summary}</p>}
                </div>
                <RotateCcw size={16} />
              </button>
            ))}
            {!replays.loading && replays.items.length === 0 && <div className="tool-empty">No replays yet.</div>}
          </div>
        </section>

        <section className="agent-lab-panel glass-soft">
          <div className="agent-lab-panel-head"><h2>Selected Replay</h2><span>{selected ? selected.id.slice(0, 8) : "empty"}</span></div>
          {selected ? (
            <>
              <div className="agent-lab-detail">
                <strong>{selected.status}</strong>
                <span>{selected.trace_run_id || "no trace"}</span>
              </div>
              <div className="agent-lab-row-actions wide">
                <button type="button" onClick={() => act("annotation", () => createReplayAnnotation(selected.id, { annotation_type: "note", content: "Review from Replay Center" }))} disabled={busy !== null}>
                  <MessageSquarePlus size={16} /> Annotate
                </button>
                <button type="button" onClick={() => act("bad-case", () => createReplayBadCase(selected.id))} disabled={busy !== null}>
                  Bad case
                </button>
                <button type="button" onClick={() => act("regression", () => createReplayRegressionCase(selected.id))} disabled={busy !== null}>
                  Regression
                </button>
              </div>
              <pre>{JSON.stringify(selected.trace_snapshot_json || {}, null, 2)}</pre>
            </>
          ) : (
            <div className="tool-empty">Select a replay.</div>
          )}
        </section>
      </div>
    </div>
  );
}
