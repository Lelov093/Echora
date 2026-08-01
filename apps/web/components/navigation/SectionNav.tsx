"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { isRouteNavItemActive, type RouteNavItem } from "@/lib/navigation/routes";

type SectionNavProps = {
  title: string;
  eyebrow?: string;
  items: RouteNavItem[];
};

export function SectionNav({ title, eyebrow, items }: SectionNavProps) {
  const pathname = usePathname();

  return (
    <div className="section-nav-shell">
      <section className="section-nav dynamic-glass" aria-label={`${title} navigation`}>
        <div className="section-nav-head">
          {eyebrow && <span className="section-nav-eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        <div className="section-nav-links">
          {items.map((item) => {
            const active = isRouteNavItemActive(pathname, item, items);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`section-nav-link ${active ? "section-nav-link-active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                <span className="section-nav-label-row">
                  <span>{item.label}</span>
                  {item.badge && <span className="section-nav-badge">{item.badge}</span>}
                </span>
                {item.description && <span className="section-nav-description">{item.description}</span>}
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}
