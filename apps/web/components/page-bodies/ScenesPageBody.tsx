"use client";

import { useMemo, useState } from "react";
import { useSharedScene } from "@/lib/hooks/useSharedScene";
import { SharedScenePanel } from "@/components/shared-scenes/SharedScenePanel";
import { SharedSceneEventList } from "@/components/shared-scenes/SharedSceneEventList";
import { SectionNav } from "@/components/navigation/SectionNav";
import { companionNavItems } from "@/lib/navigation/routes";

export default function ScenesPageBody() {
  const scenes = useSharedScene({ page_size: 50 });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected = useMemo(
    () => scenes.items.find((item) => item.id === selectedId) || scenes.items[0] || null,
    [selectedId, scenes.items],
  );

  return (
    <>
    <SectionNav title="Companions" eyebrow="Identity, co-presence, shared scenes" items={companionNavItems} />
    <main className="echora-page domain-page">
      <section className="dynamic-glass domain-page-hero">
        <div>
          <div className="domain-chip-row">
            <span className="pill-sm pill-accent">Shared Scenes</span>
            <span className="pill-sm">{scenes.loading ? "loading" : `${scenes.items.length} scenes`}</span>
          </div>
          <h1>å±åç»ååºæ¯</h1>
          <p>
            Shared scenes carry context, events, shared experience candidates, and visibility policy.
          </p>
        </div>
      </section>

      <div className="domain-two-column">
        <section className="dynamic-glass domain-panel">
          <div className="domain-panel-header">
            <div className="domain-panel-icon">S</div>
            <div>
              <h2>Scene Index</h2>
              <p>Select a shared scene to inspect its context and event history.</p>
            </div>
          </div>
          <div className="domain-list">
            {scenes.loading ? (
              <div className="domain-inline-empty">Loading shared scenes...</div>
            ) : scenes.error ? (
              <div className="domain-inline-empty">
                Shared scenes could not be loaded. <button className="glass-btn-secondary" onClick={scenes.reload}>Retry</button>
              </div>
            ) : scenes.items.length > 0 ? scenes.items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`glass-soft domain-list-card domain-select-card ${selected?.id === item.id ? "domain-selected-card" : ""}`}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="domain-list-head">
                  <div>
                    <strong>{item.scene_title}</strong>
                    <div className="domain-list-sub">{item.scene_status} / {item.scene_type}</div>
                  </div>
                  <span className="pill-sm">{item.events.length}</span>
                </div>
                <p className="domain-card-copy">{item.scene_summary || item.focal_topic || "No scene summary recorded."}</p>
              </button>
            )) : (
              <div className="domain-inline-empty">No shared scenes available.</div>
            )}
          </div>
        </section>

        {scenes.loading ? (
          <div className="domain-stack">
            <section className="glass-soft companion-feedback-panel">
              Preparing shared scene context...
            </section>
          </div>
        ) : selected && (
          <div className="domain-stack">
            <SharedScenePanel scene={selected} />
            <SharedSceneEventList events={selected.events} experiences={selected.shared_experiences} />
          </div>
        )}
      </div>
    </main>
    </>
  );
}
