"use client";

import { BrainCircuit, Link2, Shield, Sparkles } from "lucide-react";
import type {
  CompanionBoundaryProfile,
  CompanionBundle,
  CompanionIdentityProfile,
  CompanionPersonaProfile,
  CompanionRelationshipContract,
} from "@/lib/types";
import { IdentityProfilePanel } from "./IdentityProfilePanel";
import { PersonaProfilePanel } from "./PersonaProfilePanel";
import { RelationshipContractPanel } from "./RelationshipContractPanel";
import { BoundaryProfilePanel } from "./BoundaryProfilePanel";
import { CompanionLifecycleTimeline } from "./CompanionLifecycleTimeline";
import { CompanionProfileEditor } from "./CompanionProfileEditor";

interface DetailProps {
  companion: CompanionBundle;
  identity: CompanionIdentityProfile | null;
  persona: CompanionPersonaProfile | null;
  contract: CompanionRelationshipContract | null;
  boundary: CompanionBoundaryProfile | null;
  onReload: () => Promise<void>;
  onSaveCompanion: (payload: Record<string, unknown>) => Promise<unknown>;
  onSaveIdentity: (payload: Record<string, unknown>) => Promise<unknown>;
  onSavePersona: (payload: Record<string, unknown>) => Promise<unknown>;
  onSaveContract: (payload: Record<string, unknown>) => Promise<unknown>;
  onSaveBoundary: (payload: Record<string, unknown>) => Promise<unknown>;
}

export function CompanionDetail({
  companion,
  identity,
  persona,
  contract,
  boundary,
  onReload,
  onSaveCompanion,
  onSaveIdentity,
  onSavePersona,
  onSaveContract,
  onSaveBoundary,
}: DetailProps) {
  return (
    <div className="companion-detail-layout">
      <section className="dynamic-glass companion-hero-card">
        <div className="companion-hero-copy">
          <div className="companion-chip-row">
            <span className="pill-sm pill-accent">{companion.current_status}</span>
            <span className="pill-sm">{companion.current_mode}</span>
            <span className="pill-sm">{contract?.relationship_role || companion.relationship_role || "companion"}</span>
          </div>
          <h1>{identity?.display_name || companion.name}</h1>
          <p>
            {identity?.identity_summary || companion.identity_prompt || companion.base_personality || "Long-term cyber companion profile."}
          </p>
        </div>

        <div className="companion-hero-stats">
          <StatCard icon={<Sparkles size={16} strokeWidth={1.8} />} label="Identity" value={identity?.profile_status || "active"} />
          <StatCard icon={<BrainCircuit size={16} strokeWidth={1.8} />} label="Persona" value={persona?.persona_lock_level || "guarded"} />
          <StatCard icon={<Link2 size={16} strokeWidth={1.8} />} label="Contract" value={contract?.contract_status || "active"} />
          <StatCard icon={<Shield size={16} strokeWidth={1.8} />} label="Boundary" value={boundary?.global_memory_read_scope || "scoped"} />
        </div>
      </section>

      <div className="companion-detail-grid">
        <div className="companion-detail-main">
          <CompanionProfileEditor
            companion={companion}
            identity={identity}
            persona={persona}
            contract={contract}
            boundary={boundary}
            onSaveCompanion={onSaveCompanion}
            onSaveIdentity={onSaveIdentity}
            onSavePersona={onSavePersona}
            onSaveContract={onSaveContract}
            onSaveBoundary={onSaveBoundary}
          />
          <IdentityProfilePanel profile={identity} />
          <PersonaProfilePanel profile={persona} />
          <RelationshipContractPanel contract={contract} />
          <BoundaryProfilePanel boundary={boundary} />
        </div>
        <div className="companion-detail-side">
          <section className="dynamic-glass companion-panel">
            <div className="companion-panel-header">
              <div className="companion-panel-icon">L</div>
              <div>
                <h2>Lifecycle Controls</h2>
                <p>Archive and disable require an audited lifecycle endpoint. No hard delete is exposed here.</p>
              </div>
            </div>
            <div className="companion-action-row">
              <button type="button" className="glass-btn glass-btn-secondary" onClick={onReload}>Reload profile</button>
              <a className="glass-btn glass-btn-primary" href={`/conversation?companion_id=${companion.id}`}>Start conversation</a>
              <a className="glass-btn glass-btn-secondary" href={`/memory?companion_id=${companion.id}`}>Open memory</a>
              <a className="glass-btn glass-btn-secondary" href={`/presence?companion_id=${companion.id}`}>Open presence</a>
              <a className="glass-btn glass-btn-secondary" href={`/companions/${companion.id}/channels`}>Channel binding</a>
            </div>
          </section>
          <CompanionLifecycleTimeline
            companion={companion}
            identity={identity}
            persona={persona}
            contract={contract}
            boundary={boundary}
          />
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="glass-soft companion-stat-card">
      <div className="companion-stat-icon">{icon}</div>
      <div>
        <div className="companion-stat-label">{label}</div>
        <div className="companion-stat-value">{value}</div>
      </div>
    </div>
  );
}
