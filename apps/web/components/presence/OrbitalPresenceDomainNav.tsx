"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AudioLines, ListChecks, Radio, RadioTower } from "lucide-react";

const items = [
  { href: "/presence", label: "Overview & Queue", icon: ListChecks, exact: true },
  { href: "/presence/resident", label: "Resident", icon: RadioTower },
  { href: "/realtime", label: "Realtime", icon: Radio, exact: true },
  { href: "/realtime/voice", label: "Voice Readiness", icon: AudioLines },
];

export function OrbitalPresenceDomainNav() {
  const pathname = usePathname();
  return (
    <nav className="orbital-domain-domain-nav" aria-label="Presence workspace">
      <div>
        <span>Presence domain</span>
        <strong>Availability, quiet budgets, realtime state, and explicit permissions</strong>
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
