"use client";

import { useMemo, useState } from "react";
import { AlertCircle } from "lucide-react";
import { useCoPresence } from "@/lib/hooks/useCoPresence";
import { useCompanionRoster } from "@/lib/hooks/useCompanionRoster";
import { CoPresenceSpace } from "@/components/co-presence/CoPresenceSpace";
import { ParticipantAwarenessPanel } from "@/components/co-presence/ParticipantAwarenessPanel";
import { SectionNav } from "@/components/navigation/SectionNav";
import { companionNavItems } from "@/lib/navigation/routes";

export default function CoPresencePageBody() {
  const sessions = useCoPresence({ page_size: 50 });
  const roster = useCompanionRoster();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected = useMemo(
    () => sessions.items.find((item) => item.id === selectedId) || sessions.items[0] || null,
    [selectedId, sessions.items],
  );
  const loading = sessions.loading || roster.loading;
  const error = sessions.error || roster.error;

  return (
    <>
    <SectionNav title="Companions" eyebrow="Identity, co-presence, shared scenes" items={companionNavItems} />
    <main className="echora-page domain-page">
      <section className="dynamic-glass domain-page-hero">
        <div>
          <div className="domain-chip-row">
            <span className="pill-sm pill-accent">Co-Presence</span>
            <span className="pill-sm">{loading ? "loading" : `${sessions.items.length} sessions`}</span>
          </div>
          <h1>å±åå¨åºç©ºé´</h1>
          <p>
            Co-presence focuses on who is present, who participates, who observes, and what can be remembered.
          </p>
        </div>
      </section>

      <div className="domain-two-column">
        <section className="dynamic-glass domain-panel">
          <div className="domain-panel-header">
            <div className="domain-panel-icon">L</div>
            <div>
              <h2>Sessions</h2>
              <p>Select a co-presence session to inspect participants and boundaries.</p>
            </div>
          </div>
          <div className="domain-list">
            {loading ? (
              <div className="domain-inline-empty">Loading co-presence sessions...</div>
            ) : error ? (
              <div className="domain-inline-empty">
                Co-presence page could not be loaded.{" "}
                <button className="glass-btn-secondary" onClick={() => { sessions.reload(); roster.reload(); }}>Retry</button>
              </div>
            ) : sessions.items.length > 0 ? sessions.items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`glass-soft domain-list-card domain-select-card ${selected?.id === item.id ? "domain-selected-card" : ""}`}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="domain-list-head">
                  <div>
                    <strong>{item.session_title}</strong>
                    <div className="domain-list-sub">{item.session_status} / {item.session_source}</div>
                  </div>
                  <span className="pill-sm">{item.participants.length}</span>
                </div>
                <p className="domain-card-copy">{item.session_summary || item.entry_reason || "No session summary recorded."}</p>
              </button>
            )) : (
              <div className="domain-inline-empty">No co-presence sessions available.</div>
            )}
          </div>
        </section>

        <div className="domain-stack">
          {loading ? (
            <section className="glass-soft companion-feedback-panel">
              <AlertCircle size={18} strokeWidth={1.8} style={{ color: "var(--echora-text-muted)" }} />
              <p>Preparing co-presence context...</p>
            </section>
          ) : selected ? (
            <>
              <CoPresenceSpace session={selected} companions={roster.items} />
              <ParticipantAwarenessPanel participants={selected.participants} />
            </>
          ) : (
            <section className="glass-soft companion-feedback-panel">
              <AlertCircle size={18} strokeWidth={1.8} style={{ color: "var(--echora-text-muted)" }} />
              <p>No session selected.</p>
            </section>
          )}
        </div>
      </div>
    </main>
    </>
  );
}
