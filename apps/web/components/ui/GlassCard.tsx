"use client";
import { ReactNode } from "react";

export function GlassCard({ children, className = "", style = {} }: {
  children: ReactNode; className?: string; style?: React.CSSProperties;
}) {
  return (
    <div className={`rounded-xl ${className}`} style={{
      background: "rgba(255,255,255,0.07)",
      border: "1px solid rgba(255,255,255,0.14)",
      backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      padding: "1.25rem",
      ...style,
    }}>{children}</div>
  );
}
