"use client";

import { useState } from "react";
import { Save } from "lucide-react";
import type {
  CompanionBoundaryProfile,
  CompanionBundle,
  CompanionIdentityProfile,
  CompanionPersonaProfile,
  CompanionRelationshipContract,
} from "@/lib/types";

type SaveFn = (payload: Record<string, unknown>) => Promise<unknown>;

type CompanionProfileEditorProps = {
  companion: CompanionBundle;
  identity: CompanionIdentityProfile | null;
  persona: CompanionPersonaProfile | null;
  contract: CompanionRelationshipContract | null;
  boundary: CompanionBoundaryProfile | null;
  onSaveCompanion: SaveFn;
  onSaveIdentity: SaveFn;
  onSavePersona: SaveFn;
  onSaveContract: SaveFn;
  onSaveBoundary: SaveFn;
};

type SaveState = Record<string, "idle" | "saving" | "saved" | "error">;

function csv(values?: unknown[]) {
  return (values ?? []).map((item) => String(item)).filter(Boolean).join(", ");
}

function splitCsv(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export function CompanionProfileEditor({
  companion,
  identity,
  persona,
  contract,
  boundary,
  onSaveCompanion,
  onSaveIdentity,
  onSavePersona,
  onSaveContract,
  onSaveBoundary,
}: CompanionProfileEditorProps) {
  const [state, setState] = useState<SaveState>({});
  const [basic, setBasic] = useState({
    name: companion.name,
    subtitle: companion.subtitle ?? "",
    identity_prompt: companion.identity_prompt ?? "",
    base_personality: companion.base_personality ?? "",
    current_focus: companion.current_focus ?? "",
  });
  const [identityForm, setIdentityForm] = useState({
    display_name: identity?.display_name ?? companion.name,
    identity_summary: identity?.identity_summary ?? "",
    self_continuity_summary: identity?.self_continuity_summary ?? "",
    origin_story: identity?.origin_story ?? "",
    core_traits_json: csv(identity?.core_traits_json),
    identity_labels_json: csv(identity?.identity_labels_json),
  });
  const [personaForm, setPersonaForm] = useState({
    persona_summary: persona?.persona_summary ?? "",
    communication_style_summary: persona?.communication_style_summary ?? "",
    persona_lock_level: persona?.persona_lock_level ?? "guarded",
    drift_guard_level: persona?.drift_guard_level ?? "standard",
    presence_style: persona?.presence_style ?? "balanced",
    tone_descriptors_json: csv(persona?.tone_descriptors_json),
    core_values_json: csv(persona?.core_values_json),
  });
  const [contractForm, setContractForm] = useState({
    relationship_role: contract?.relationship_role ?? "companion",
    contract_summary: contract?.contract_summary ?? "",
    collaboration_style_summary: contract?.collaboration_style_summary ?? "",
    shared_memory_policy: contract?.shared_memory_policy ?? "candidate_review",
    cross_companion_disclosure_policy: contract?.cross_companion_disclosure_policy ?? "review_required",
    support_scope_json: csv(contract?.support_scope_json),
  });
  const [boundaryForm, setBoundaryForm] = useState({
    private_memory_default: boundary?.private_memory_default ?? "private_companion_only",
    shared_memory_default: boundary?.shared_memory_default ?? "candidate_review",
    global_memory_read_scope: boundary?.global_memory_read_scope ?? "low_risk_summary_only",
    cross_companion_read_policy: boundary?.cross_companion_read_policy ?? "blocked",
    presence_interrupt_policy: boundary?.presence_interrupt_policy ?? "respect_existing_boundary",
    review_required_private_to_shared: boundary?.review_required_private_to_shared ?? true,
    review_required_shared_to_private: boundary?.review_required_shared_to_private ?? true,
    review_required_cross_companion_share: boundary?.review_required_cross_companion_share ?? true,
  });

  const runSave = async (key: string, fn: SaveFn, payload: Record<string, unknown>) => {
    setState((current) => ({ ...current, [key]: "saving" }));
    try {
      await fn(payload);
      setState((current) => ({ ...current, [key]: "saved" }));
      setTimeout(() => setState((current) => ({ ...current, [key]: "idle" })), 1800);
    } catch {
      setState((current) => ({ ...current, [key]: "error" }));
    }
  };

  return (
    <section className="dynamic-glass companion-panel companion-editor">
      <div className="companion-panel-header">
        <div className="companion-panel-icon"><Save size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Profile Editor</h2>
          <p>Edits persist through existing Companion and identity/persona/relationship/boundary APIs.</p>
        </div>
      </div>

      <EditorSection
        title="Basic Profile"
        state={state.basic}
        onSave={() => runSave("basic", onSaveCompanion, {
          ...basic,
          subtitle: basic.subtitle || null,
          identity_prompt: basic.identity_prompt || null,
          base_personality: basic.base_personality || null,
          current_focus: basic.current_focus || null,
        })}
      >
        <Field label="Name" value={basic.name} onChange={(value) => setBasic((current) => ({ ...current, name: value }))} />
        <Field label="Subtitle" value={basic.subtitle} onChange={(value) => setBasic((current) => ({ ...current, subtitle: value }))} />
        <Field label="Identity prompt" value={basic.identity_prompt} onChange={(value) => setBasic((current) => ({ ...current, identity_prompt: value }))} multiline />
        <Field label="Base personality" value={basic.base_personality} onChange={(value) => setBasic((current) => ({ ...current, base_personality: value }))} multiline />
        <Field label="Current focus" value={basic.current_focus} onChange={(value) => setBasic((current) => ({ ...current, current_focus: value }))} />
      </EditorSection>

      <EditorSection
        title="Identity"
        state={state.identity}
        onSave={() => runSave("identity", onSaveIdentity, {
          ...identityForm,
          core_traits_json: splitCsv(identityForm.core_traits_json),
          identity_labels_json: splitCsv(identityForm.identity_labels_json),
        })}
      >
        <Field label="Display name" value={identityForm.display_name} onChange={(value) => setIdentityForm((current) => ({ ...current, display_name: value }))} />
        <Field label="Identity summary" value={identityForm.identity_summary} onChange={(value) => setIdentityForm((current) => ({ ...current, identity_summary: value }))} multiline />
        <Field label="Self-continuity" value={identityForm.self_continuity_summary} onChange={(value) => setIdentityForm((current) => ({ ...current, self_continuity_summary: value }))} multiline />
        <Field label="Origin story" value={identityForm.origin_story} onChange={(value) => setIdentityForm((current) => ({ ...current, origin_story: value }))} multiline />
        <Field label="Traits (comma separated)" value={identityForm.core_traits_json} onChange={(value) => setIdentityForm((current) => ({ ...current, core_traits_json: value }))} />
        <Field label="Labels (comma separated)" value={identityForm.identity_labels_json} onChange={(value) => setIdentityForm((current) => ({ ...current, identity_labels_json: value }))} />
      </EditorSection>

      <EditorSection
        title="Persona"
        state={state.persona}
        onSave={() => runSave("persona", onSavePersona, {
          ...personaForm,
          tone_descriptors_json: splitCsv(personaForm.tone_descriptors_json),
          core_values_json: splitCsv(personaForm.core_values_json),
        })}
      >
        <Field label="Persona summary" value={personaForm.persona_summary} onChange={(value) => setPersonaForm((current) => ({ ...current, persona_summary: value }))} multiline />
        <Field label="Communication style" value={personaForm.communication_style_summary} onChange={(value) => setPersonaForm((current) => ({ ...current, communication_style_summary: value }))} multiline />
        <Field label="Persona lock" value={personaForm.persona_lock_level} onChange={(value) => setPersonaForm((current) => ({ ...current, persona_lock_level: value }))} />
        <Field label="Drift guard" value={personaForm.drift_guard_level} onChange={(value) => setPersonaForm((current) => ({ ...current, drift_guard_level: value }))} />
        <Field label="Presence style" value={personaForm.presence_style} onChange={(value) => setPersonaForm((current) => ({ ...current, presence_style: value }))} />
        <Field label="Tone descriptors" value={personaForm.tone_descriptors_json} onChange={(value) => setPersonaForm((current) => ({ ...current, tone_descriptors_json: value }))} />
        <Field label="Core values" value={personaForm.core_values_json} onChange={(value) => setPersonaForm((current) => ({ ...current, core_values_json: value }))} />
      </EditorSection>

      <EditorSection
        title="Relationship Contract"
        state={state.contract}
        onSave={() => runSave("contract", onSaveContract, {
          ...contractForm,
          support_scope_json: splitCsv(contractForm.support_scope_json),
        })}
      >
        <Field label="Relationship role" value={contractForm.relationship_role} onChange={(value) => setContractForm((current) => ({ ...current, relationship_role: value }))} />
        <Field label="Contract summary" value={contractForm.contract_summary} onChange={(value) => setContractForm((current) => ({ ...current, contract_summary: value }))} multiline />
        <Field label="Collaboration style" value={contractForm.collaboration_style_summary} onChange={(value) => setContractForm((current) => ({ ...current, collaboration_style_summary: value }))} multiline />
        <Field label="Shared memory policy" value={contractForm.shared_memory_policy} onChange={(value) => setContractForm((current) => ({ ...current, shared_memory_policy: value }))} />
        <Field label="Cross-companion disclosure" value={contractForm.cross_companion_disclosure_policy} onChange={(value) => setContractForm((current) => ({ ...current, cross_companion_disclosure_policy: value }))} />
        <Field label="Support scope" value={contractForm.support_scope_json} onChange={(value) => setContractForm((current) => ({ ...current, support_scope_json: value }))} />
      </EditorSection>

      <EditorSection
        title="Boundary"
        state={state.boundary}
        onSave={() => runSave("boundary", onSaveBoundary, boundaryForm)}
      >
        <Field label="Private memory default" value={boundaryForm.private_memory_default} onChange={(value) => setBoundaryForm((current) => ({ ...current, private_memory_default: value }))} />
        <Field label="Shared memory default" value={boundaryForm.shared_memory_default} onChange={(value) => setBoundaryForm((current) => ({ ...current, shared_memory_default: value }))} />
        <Field label="Global memory read scope" value={boundaryForm.global_memory_read_scope} onChange={(value) => setBoundaryForm((current) => ({ ...current, global_memory_read_scope: value }))} />
        <Field label="Cross-companion read policy" value={boundaryForm.cross_companion_read_policy} onChange={(value) => setBoundaryForm((current) => ({ ...current, cross_companion_read_policy: value }))} />
        <Field label="Presence interrupt policy" value={boundaryForm.presence_interrupt_policy} onChange={(value) => setBoundaryForm((current) => ({ ...current, presence_interrupt_policy: value }))} />
        <Check label="Private to shared requires review" checked={boundaryForm.review_required_private_to_shared} onChange={(value) => setBoundaryForm((current) => ({ ...current, review_required_private_to_shared: value }))} />
        <Check label="Shared to private requires review" checked={boundaryForm.review_required_shared_to_private} onChange={(value) => setBoundaryForm((current) => ({ ...current, review_required_shared_to_private: value }))} />
        <Check label="Cross-companion share requires review" checked={boundaryForm.review_required_cross_companion_share} onChange={(value) => setBoundaryForm((current) => ({ ...current, review_required_cross_companion_share: value }))} />
      </EditorSection>
    </section>
  );
}

function EditorSection({ title, state, onSave, children }: {
  title: string;
  state?: "idle" | "saving" | "saved" | "error";
  onSave: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="companion-editor-section">
      <div className="companion-editor-section-head">
        <h3>{title}</h3>
        <div className="companion-form-actions">
          {state && state !== "idle" && <span className="companion-form-message">{state}</span>}
          <button type="button" className="glass-btn glass-btn-secondary" onClick={onSave} disabled={state === "saving"}>
            {state === "saving" ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
      <div className="companion-form-grid">{children}</div>
    </div>
  );
}

function Field({ label, value, onChange, multiline }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  return (
    <label className="companion-form-field">
      <span>{label}</span>
      {multiline ? (
        <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={3} />
      ) : (
        <input value={value} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  );
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="companion-check-editor">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}
