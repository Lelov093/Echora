"use client";

import { CalendarClock, NotebookPen } from "lucide-react";
import type { SharedExperienceRecord, SharedSceneEvent } from "@/lib/types";

export function SharedSceneEventList({
  events,
  experiences,
}: {
  events: SharedSceneEvent[];
  experiences: SharedExperienceRecord[];
}) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><NotebookPen size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>SharedSceneEventList</h2>
          <p>记录共同发生了什么，以及哪些事件已经转成 review-gated shared experience candidate。</p>
        </div>
      </div>

      <div className="domain-list">
        {events.length > 0 ? events.map((event) => {
          const experience = experiences.find((item) => item.source_scene_event_id === event.id);
          return (
            <div key={event.id} className="glass-soft domain-list-card">
              <div className="domain-list-head">
                <div>
                  <strong>{event.title}</strong>
                  <div className="domain-list-sub">{event.event_type} · {event.event_source}</div>
                </div>
                <span className="pill-sm">{event.visibility_scope}</span>
              </div>

              <p className="domain-card-copy">{event.content || "No event content."}</p>
              <div className="domain-inline-row">
                <CalendarClock size={13} strokeWidth={1.8} />
                <span>{event.occurred_at ? new Date(event.occurred_at).toLocaleString() : "Time unavailable"}</span>
              </div>
              {experience && (
                <div className="domain-linked-note">
                  Experience candidate: {experience.experience_status} · review {experience.review_required ? "required" : "optional"}
                </div>
              )}
            </div>
          );
        }) : (
          <div className="domain-inline-empty">No shared scene events yet.</div>
        )}
      </div>
    </section>
  );
}
