"use client";
const colors: Record<string, { bg: string; text: string }> = {
  active: { bg: "rgba(79,172,254,0.20)", text: "#4FACFE" },
  pending: { bg: "rgba(184,182,229,0.20)", text: "#B9B6E5" },
  queued: { bg: "rgba(79,172,254,0.15)", text: "#89F7FE" },
  accepted: { bg: "rgba(104,224,207,0.20)", text: "#68E0CF" },
  committed: { bg: "rgba(79,172,254,0.25)", text: "#4FACFE" },
  rejected: { bg: "rgba(248,187,208,0.20)", text: "#F8BBD0" },
  completed: { bg: "rgba(79,172,254,0.20)", text: "#4FACFE" },
  candidate: { bg: "rgba(184,182,229,0.18)", text: "#B9B6E5" },
  dormant: { bg: "rgba(203,213,225,0.15)", text: "#CBD5E1" },
  suppressed: { bg: "rgba(203,213,225,0.12)", text: "#94A3B8" },
  archived: { bg: "rgba(203,213,225,0.10)", text: "#64748B" },
  dismissed: { bg: "rgba(203,213,225,0.10)", text: "#94A3B8" },
  reverted: { bg: "rgba(248,187,208,0.15)", text: "#F8BBD0" },
  failed: { bg: "rgba(248,187,208,0.20)", text: "#F8BBD0" },
  deleted: { bg: "rgba(248,187,208,0.10)", text: "#F8BBD0" },
};
export function StatusBadge({ status }: { status: string }) {
  const c = colors[status] || { bg: "rgba(255,255,255,0.08)", text: "#CBD5E1" };
  return <span style={{
    display: "inline-block", padding: "0.15rem 0.6rem", borderRadius: "9999px",
    fontSize: "0.7rem", fontWeight: 500, background: c.bg, color: c.text,
    border: `1px solid ${c.text}20`,
  }}>{status}</span>;
}
