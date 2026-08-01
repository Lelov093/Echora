"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Cable, ClipboardCheck, MemoryStick, ShieldCheck } from "lucide-react";

const items = [
  { href: "/settings/channels", label: "Gateway", icon: Cable, exact: true },
  { href: "/settings/channels/discord", label: "Discord", icon: Bot },
  { href: "/memory/channel-candidates", label: "Memory Review", icon: MemoryStick },
  { href: "/trace/channel-audit", label: "Audit", icon: ClipboardCheck },
  { href: "/settings/permissions", label: "Permissions", icon: ShieldCheck },
];

export function OrbitalChannelsDomainNav() {
  const pathname = usePathname();
  return (
    <nav className="orbital-advanced-domain-nav" aria-label="Channel and system workspace">
      <div>
        <span>Channel &amp; system workspace</span>
        <strong>Provider readiness, identity binding, review gates, audit, and hard stop</strong>
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
