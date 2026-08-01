"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertTriangle, FlaskConical, FolderKanban, PlayCircle, Wrench } from "lucide-react";

const items = [
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/tools", label: "Tools", icon: Wrench },
  { href: "/evaluation", label: "Evaluation", icon: FlaskConical },
  { href: "/bad-cases", label: "Bad Cases", icon: AlertTriangle },
  { href: "/replays", label: "Replay", icon: PlayCircle },
];

export function OrbitalStudioDomainNav() {
  const pathname = usePathname();
  return (
    <nav className="orbital-advanced-domain-nav" aria-label="Studio quality workspace">
      <div>
        <span>Studio workspace</span>
        <strong>Projects, controlled execution, evaluation, regression, and replay</strong>
      </div>
      <div className="orbital-advanced-domain-links">
        {items.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined}>
              <Icon size={15} />
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
