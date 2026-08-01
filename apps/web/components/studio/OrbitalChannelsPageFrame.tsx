import type { ReactNode } from "react";
import { EyeOff, ShieldCheck } from "lucide-react";
import { OrbitalChannelsDomainNav } from "./OrbitalChannelsDomainNav";

export function OrbitalChannelsPageFrame({
  eyebrow,
  title,
  description,
  children,
  scope = "All Companions",
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  scope?: string;
}) {
  return (
    <div className="orbital-advanced-page orbital-advanced-embedded-workspace orbital-advanced-channel-workspace">
      <OrbitalChannelsDomainNav />
      <header className="orbital-advanced-page-header">
        <div>
          <span>{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <div className="orbital-advanced-context">
          <span><ShieldCheck size={14} /> {scope}</span>
          <span><EyeOff size={14} /> Secrets remain write-only</span>
        </div>
      </header>
      <div className="orbital-advanced-embedded-body">{children}</div>
    </div>
  );
}
