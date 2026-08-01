"use client";
import { ReactNode } from "react";

export function PageShell({ title, children }: { title: string; children: ReactNode }) {
  return <div style={{ maxWidth: 1200, margin: "0 auto", padding: "1.5rem 2rem" }}>
    <h1 style={{ color: "#F8FAFC", fontSize: "1.4rem", fontWeight: 300, marginBottom: "1.5rem", letterSpacing: "0.02em" }}>{title}</h1>
    {children}
  </div>;
}
