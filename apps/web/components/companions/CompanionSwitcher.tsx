"use client";

import Link from "next/link";
import { Users } from "lucide-react";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";
import { ALL_COMPANIONS_ID } from "@/lib/stores/appStore";

type CompanionSwitcherProps = {
  compact?: boolean;
};

export function CompanionSwitcher({ compact = false }: CompanionSwitcherProps) {
  const ctx = useActiveCompanionContext();

  if (ctx.loading) {
    return <div className={compact ? "companion-switcher compact" : "companion-switcher"}>Loading companions...</div>;
  }

  if (ctx.error) {
    return (
      <Link className={compact ? "companion-switcher compact" : "companion-switcher"} href="/companions">
        Companions unavailable
      </Link>
    );
  }

  if (ctx.companions.length === 0) {
    return (
      <Link className={compact ? "companion-switcher compact" : "companion-switcher"} href="/companions">
        No companions
      </Link>
    );
  }

  return (
    <label className={compact ? "companion-switcher compact" : "companion-switcher"}>
      <span className="companion-switcher-icon" aria-hidden="true">
        <Users size={14} strokeWidth={1.8} />
      </span>
      <span className="companion-switcher-copy">
        {!compact && <span className="companion-switcher-label">Active companion</span>}
        <select
          value={ctx.selectedCompanionValue}
          onChange={(event) => ctx.setActiveCompanionId(event.target.value)}
          aria-label="Active companion"
        >
          <option value={ALL_COMPANIONS_ID}>All Companions</option>
          {ctx.companions.map((companion) => (
            <option key={companion.id} value={companion.id}>
              {companion.name}
            </option>
          ))}
        </select>
      </span>
    </label>
  );
}
