"use client";

import { BellRing, Moon, Radio, Send } from "lucide-react";
import type { CoPresenceInvitationRecord, MeaningfulSilenceResult, ResidentStatusRecord } from "@/lib/types";

interface Props {
  status: ResidentStatusRecord | null;
  invitation: CoPresenceInvitationRecord | null;
  silence: MeaningfulSilenceResult | null;
  saving?: boolean;
  error?: string | null;
  onSetAvailable?: () => Promise<unknown>;
  onInvite?: () => Promise<unknown>;
  onSilence?: () => Promise<unknown>;
}

export function ResidentPresencePanel({ status, invitation, silence, saving, error, onSetAvailable, onInvite, onSilence }: Props) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Radio size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Resident Presence</h2>
          <p>Explicit companion availability, invitation, and meaningful silence controls.</p>
        </div>
      </div>

      <div className="domain-action-row">
        <button className="act-btn" onClick={onSetAvailable} disabled={!onSetAvailable || saving}>
          <BellRing size={14} /> Set available
        </button>
        <button className="act-btn glass-btn-secondary" onClick={onInvite} disabled={!onInvite || saving}>
          <Send size={14} /> Create invitation
        </button>
        <button className="act-btn glass-btn-secondary" onClick={onSilence} disabled={!onSilence || saving}>
          <Moon size={14} /> Meaningful silence
        </button>
      </div>

      {error && <div className="domain-linked-note">{error}</div>}

      <div className="domain-mini-grid">
        <div>
          <div className="domain-detail-label">Current status</div>
          <pre className="domain-code-block">{JSON.stringify(status ?? {}, null, 2)}</pre>
        </div>
        <div>
          <div className="domain-detail-label">Latest invitation</div>
          <pre className="domain-code-block">{JSON.stringify(invitation ?? {}, null, 2)}</pre>
        </div>
        <div>
          <div className="domain-detail-label">Meaningful silence</div>
          <pre className="domain-code-block">{JSON.stringify(silence ?? {}, null, 2)}</pre>
        </div>
      </div>
    </section>
  );
}
