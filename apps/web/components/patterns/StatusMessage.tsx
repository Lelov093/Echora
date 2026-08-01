import type { ReactNode } from "react";

export function StatusMessage({
  children,
  tone = "info",
  className = "",
}: {
  children: ReactNode;
  tone?: "info" | "success" | "error";
  className?: string;
}) {
  return (
    <div
      className={`orbital-status-message is-${tone} ${className}`.trim()}
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : "polite"}
      aria-atomic="true"
    >
      {children}
    </div>
  );
}
