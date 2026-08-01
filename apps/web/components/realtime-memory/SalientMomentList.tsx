"use client";

import { Sparkles } from "lucide-react";
import type { JsonObject, RealtimeMemoryBufferBundle } from "@/lib/types";

function itemId(item: JsonObject) {
  return typeof item.id === "string" ? item.id : "";
}

function itemSummary(item: JsonObject) {
  return String(item.content_summary ?? item.summary ?? item.source_type ?? "Realtime buffer item");
}

export function SalientMomentList({
  buffer,
  onDetect,
}: {
  buffer: RealtimeMemoryBufferBundle | null;
  onDetect?: (bufferItemId: string) => Promise<void>;
}) {
  const items = buffer?.items ?? [];

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Sparkles size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Salient Moments</h2>
          <p>Detected moments become candidates for review, not automatic memory writes.</p>
        </div>
      </div>

      <div className="domain-list">
        {items.length === 0 ? (
          <div className="domain-inline-empty">No buffer items are available for salient moment detection.</div>
        ) : items.map((item, index) => {
          const id = itemId(item);
          return (
            <div key={id || index} className="glass-soft domain-list-card">
              <div className="domain-list-head">
                <div>
                  <strong>{itemSummary(item)}</strong>
                  <div className="domain-list-sub">
                    {String(item.item_status ?? "buffered")} · {String(item.retention_policy ?? "ephemeral")}
                  </div>
                </div>
                <button className="act-btn glass-btn-secondary" onClick={() => id && onDetect?.(id)} disabled={!id || !onDetect}>
                  Detect
                </button>
              </div>
              <div className="domain-chip-row">
                <span className="pill-sm">long-term write {String(item.can_write_long_term_memory ?? false)}</span>
                <span className="pill-sm">candidate allowed {String(item.can_generate_salient_moment ?? true)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
