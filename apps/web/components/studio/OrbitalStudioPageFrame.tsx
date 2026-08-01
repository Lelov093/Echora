import type { ReactNode } from "react";
import { Boxes, ShieldCheck } from "lucide-react";
import { OrbitalStudioDomainNav } from "./OrbitalStudioDomainNav";

export function OrbitalStudioPageFrame({
  eyebrow,
  title,
  description,
  children,
  scope = "Companion-aware",
  policy,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  scope?: string;
  policy?: string;
}) {
  return (
    <div className="orbital-advanced-page orbital-advanced-embedded-workspace">
      <OrbitalStudioDomainNav />
      <header className="orbital-advanced-page-header">
        <div>
          <span>{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <div className="orbital-advanced-context">
          <span><Boxes size={14} /> {scope}</span>
          <span><ShieldCheck size={14} /> {policy || "Review gates active"}</span>
        </div>
      </header>
      <div className="orbital-advanced-embedded-body">{children}</div>
    </div>
  );
}
