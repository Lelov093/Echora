import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export function SettingsViewHeader({ eyebrow, title, description, icon: Icon, aside }: {
  eyebrow: string;
  title: string;
  description: string;
  icon?: LucideIcon;
  aside?: ReactNode;
}) {
  return (
    <header className="settings-view-header">
      <div>
        <p>{eyebrow}</p>
        <h1>{title}</h1>
        <span>{description}</span>
      </div>
      {aside ? <aside>{Icon ? <Icon size={18} aria-hidden="true" /> : null}{aside}</aside> : null}
    </header>
  );
}

export function SettingsSection({ title, description, children, className = "" }: {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`settings-view-section ${className}`.trim()}>
      <header><h2>{title}</h2>{description ? <p>{description}</p> : null}</header>
      <div>{children}</div>
    </section>
  );
}
