"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { History, ListRestart, Network, Radio, ScrollText } from "lucide-react";

const items = [
  { href: "/trace", label: "Overview", icon: Network, exact: true },
  { href: "/trace/realtime", label: "Realtime Trace", icon: Radio, exact: true },
  { href: "/replays", label: "Run Replay", icon: History, exact: true },
  { href: "/trace/realtime/replay", label: "Realtime Replay", icon: ListRestart },
  { href: "/trace/channel-audit", label: "Channel Audit", icon: ScrollText },
];

export function OrbitalTraceDomainNav() {
  const pathname = usePathname();
  return (
    <nav className="orbital-advanced-domain-nav" aria-label="Trace and replay workspace">
      <div>
        <span>Evidence workspace</span>
        <strong>Trace paths, redacted replay, channel audit, and regression evidence</strong>
      </div>
      <div className="orbital-advanced-domain-links">
        {items.map((item) => {
          const Icon = item.icon;
          const active = item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
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
