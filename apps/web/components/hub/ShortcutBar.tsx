"use client";

const shortcuts = [
  ["/conversation", "Conversation"],
  ["/memory", "Memory Center"],
  ["/growth", "Growth Journal"],
  ["/presence", "Presence Queue"],
  ["/settings", "Boundary Studio"],
];

export function ShortcutBar() {
  return (
    <div className="glass-shortcut" style={{ height: 56, display: "flex", alignItems: "center", justifyContent: "center", gap: 14, padding: "0 20px" }}>
      {shortcuts.map(([href, label]) => (
        <a key={href} href={href} className="glass-lift" style={{
          padding: "8px 22px", borderRadius: 9999, fontSize: "0.82rem",
          background: "rgba(255,255,255,0.46)", border: "1px solid rgba(255,255,255,0.56)",
          color: "var(--echora-text-secondary)", textDecoration: "none", fontWeight: 400,
          transition: "transform 0.15s, border-color 0.15s",
        }}>
          {label}
        </a>
      ))}
    </div>
  );
}
