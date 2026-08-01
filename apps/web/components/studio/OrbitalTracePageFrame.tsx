import type { ReactNode } from "react";
import { EyeOff, Layers3 } from "lucide-react";
import { OrbitalTraceDomainNav } from "./OrbitalTraceDomainNav";

export function OrbitalTracePageFrame({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <div className="orbital-advanced-page orbital-advanced-embedded-workspace orbital-advanced-trace-workspace">
      <OrbitalTraceDomainNav />
      <header className="orbital-advanced-page-header">
        <div>
          <span>{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <div className="orbital-advanced-context">
          <span><Layers3 size={14} /> All Companions, labeled by scope</span>
          <span><EyeOff size={14} /> Redaction enforced</span>
        </div>
      </header>
      <div className="orbital-advanced-embedded-body">{children}</div>
    </div>
  );
}
