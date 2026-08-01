"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowLeft, Eye, Orbit, UsersRound } from "lucide-react";
import { CoPresenceSpace } from "@/components/co-presence/CoPresenceSpace";
import { ParticipantAwarenessPanel } from "@/components/co-presence/ParticipantAwarenessPanel";
import { DataState } from "@/components/patterns/DataState";
import { useCoPresence } from "@/lib/hooks/useCoPresence";
import { useCompanionRoster } from "@/lib/hooks/useCompanionRoster";

export function OrbitalCoPresencePage() {
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
    <main className="orbital-domain-page">
      <Link className="orbital-domain-back" href="/?mode=multi"><ArrowLeft size={15} />返回 Multi Companion</Link>
      <header className="orbital-domain-page-header">
        <div>
          <span>Studio / Participation map</span>
          <h1>Co-Presence</h1>
          <p>Inspect who is present, who may speak, and which memory permissions apply to each participant.</p>
        </div>
        <div className="orbital-domain-header-stat"><Orbit size={17} /><strong>{sessions.items.length}</strong><span>sessions</span></div>
      </header>

      {loading ? (
        <DataState kind="loading" title="Loading co-presence sessions" description="Resolving participant and boundary context." />
      ) : error ? (
        <DataState
          kind="error"
          title="Co-presence unavailable"
          description={error}
          action={<button className="orbital-domain-secondary" onClick={() => { void sessions.reload(); void roster.reload(); }}>Try again</button>}
        />
      ) : (
        <div className="orbital-domain-workbench">
          <section className="orbital-domain-index-panel">
            <div className="orbital-domain-panel-heading">
              <div><span>Session index</span><h2>Presence contexts</h2></div>
              <UsersRound size={18} />
            </div>
            <div className="orbital-domain-index-list">
              {sessions.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={selected?.id === item.id ? "active" : ""}
                  onClick={() => setSelectedId(item.id)}
                >
                  <span className="orbital-domain-avatar"><Eye size={16} /></span>
                  <span>
                    <strong>{item.session_title}</strong>
                    <small>{item.session_status} · {item.session_source}</small>
                  </span>
                  <em>{item.participants.length}</em>
                </button>
              ))}
              {sessions.items.length === 0 ? <div className="orbital-domain-empty">No co-presence sessions are available.</div> : null}
            </div>
          </section>
          <div className="orbital-domain-detail-stack">
            {selected ? (
              <>
                <CoPresenceSpace session={selected} companions={roster.items} />
                <ParticipantAwarenessPanel participants={selected.participants} />
              </>
            ) : <div className="orbital-domain-empty">Select a session to inspect participants and memory permissions.</div>}
          </div>
        </div>
      )}
    </main>
  );
}
