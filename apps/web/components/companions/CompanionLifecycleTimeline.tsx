"use client";

import { Clock3 } from "lucide-react";
import type {
  CompanionBoundaryProfile,
  CompanionBundle,
  CompanionIdentityProfile,
  CompanionPersonaProfile,
  CompanionRelationshipContract,
} from "@/lib/types";

interface LifecycleProps {
  companion: CompanionBundle;
  identity: CompanionIdentityProfile | null;
  persona: CompanionPersonaProfile | null;
  contract: CompanionRelationshipContract | null;
  boundary: CompanionBoundaryProfile | null;
}

export function CompanionLifecycleTimeline({ companion, identity, persona, contract, boundary }: LifecycleProps) {
  const items = [
    {
      key: "created",
      title: "Companion created",
      detail: `${companion.name} entered the roster as a persistent cyber companion.`,
      at: companion.created_at || companion.updated_at || null,
    },
    identity ? {
      key: "identity",
      title: "Identity profile aligned",
      detail: identity.identity_summary || "Identity profile available.",
      at: identity.updated_at,
    } : null,
    persona ? {
      key: "persona",
      title: "Persona guard established",
      detail: `Lock ${persona.persona_lock_level}, drift ${persona.drift_guard_level}, presence ${persona.presence_style}.`,
      at: persona.updated_at,
    } : null,
    contract ? {
      key: "contract",
      title: "Relationship contract active",
      detail: contract.contract_summary || `Role ${contract.relationship_role}.`,
      at: contract.updated_at,
    } : null,
    boundary ? {
      key: "boundary",
      title: "Boundary profile scoped",
      detail: `Global memory ${boundary.global_memory_read_scope}; cross-companion ${boundary.cross_companion_read_policy}.`,
      at: boundary.updated_at,
    } : null,
  ].filter(isTimelineItem).sort((a, b) => new Date(a.at ?? 0).getTime() - new Date(b.at ?? 0).getTime());

  type TimelineItem = {
    key: string;
    title: string;
    detail: string;
    at: string | null;
  };

  function isTimelineItem(value: TimelineItem | null): value is TimelineItem {
    return value !== null;
  }

  return (
    <section className="dynamic-glass companion-panel">
      <div className="companion-panel-header">
        <div className="companion-panel-icon"><Clock3 size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Lifecycle Timeline</h2>
          <p>根据伙伴档案与关系更新时间生成。</p>
        </div>
      </div>

      <div className="companion-timeline">
        {items.map((item) => (
          <div key={item.key} className="companion-timeline-item">
            <div className="companion-timeline-dot" />
            <div className="companion-timeline-content">
              <div className="companion-timeline-head">
                <strong>{item.title}</strong>
                <span>{item.at ? new Date(item.at).toLocaleString() : "Time unavailable"}</span>
              </div>
              <p>{item.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
