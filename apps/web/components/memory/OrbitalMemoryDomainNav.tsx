"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrainCircuit, Database, GitCompareArrows, RadioTower, Waypoints } from "lucide-react";

const items = [
  { href: "/memory", label: "Workspace", icon: Database, exact: true },
  { href: "/memory/shared", label: "Shared Review", icon: GitCompareArrows },
  { href: "/memory/realtime-buffer", label: "Realtime Buffer", icon: RadioTower },
  { href: "/growth", label: "Growth", icon: BrainCircuit },
  { href: "/memory/channel-candidates", label: "Channel Review", icon: Waypoints },
];

export function OrbitalMemoryDomainNav() {
  const pathname = usePathname();
  return (
    <nav className="orbital-domain-domain-nav" aria-label="Memory workspace">
      <div>
        <span>Memory domain</span>
        <strong>Scope, review policy, evidence, and reversible decisions</strong>
      </div>
      <div className="orbital-domain-domain-links">
        {items.map((item) => {
          const active = item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
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
