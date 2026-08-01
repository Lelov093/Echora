"use client";

export function CIPillar() {
  return (
    <div className="glass-mini" style={{ padding: 20, minHeight: 132 }}>
      <div style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--echora-text-muted)", marginBottom: 6 }}>
        Boundary Summary
      </div>
      <p style={{ fontSize: "0.85rem", color: "var(--echora-text-secondary)", margin: 0 }}>
        Memory commit requires user review. Settings are active.
      </p>
    </div>
  );
}
