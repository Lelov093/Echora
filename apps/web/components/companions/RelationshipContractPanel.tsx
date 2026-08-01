"use client";

import { Handshake } from "lucide-react";
import type { CompanionRelationshipContract } from "@/lib/types";

export function RelationshipContractPanel({ contract }: { contract: CompanionRelationshipContract | null }) {
  const supportScope = contract?.support_scope_json?.map((item) => String(item)).filter(Boolean) ?? [];

  return (
    <section className="dynamic-glass companion-panel">
      <div className="companion-panel-header">
        <div className="companion-panel-icon"><Handshake size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Relationship Contract</h2>
          <p>Relationship role, disclosure policy, and how this companion is expected to collaborate.</p>
        </div>
      </div>

      {contract ? (
        <div className="companion-panel-body">
          <div className="companion-chip-row">
            <span className="pill-sm">{contract.relationship_role}</span>
            <span className="pill-sm">{contract.contract_status}</span>
            <span className="pill-sm">shared {contract.shared_memory_policy}</span>
          </div>
          <Block label="Contract Summary" value={contract.contract_summary || "No contract summary recorded yet."} />
          <Block label="Collaboration Style" value={contract.collaboration_style_summary || "No collaboration style summary recorded yet."} />
          <Block label="Cross-Companion Disclosure" value={contract.cross_companion_disclosure_policy} />
          <div className="companion-detail-block">
            <div className="companion-detail-label">Support Scope</div>
            <div className="companion-chip-row">
              {supportScope.length > 0 ? supportScope.map((item) => <span key={item} className="pill-sm">{item}</span>) : <span className="companion-inline-empty">No scope items recorded</span>}
            </div>
          </div>
        </div>
      ) : (
        <div className="companion-panel-empty">Relationship contract is not available.</div>
      )}
    </section>
  );
}

function Block({ label, value }: { label: string; value: string }) {
  return (
    <div className="companion-detail-block">
      <div className="companion-detail-label">{label}</div>
      <div className="companion-detail-value">{value}</div>
    </div>
  );
}
