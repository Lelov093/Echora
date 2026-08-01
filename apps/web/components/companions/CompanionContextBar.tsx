"use client";

import Link from "next/link";
import { HeartHandshake } from "lucide-react";
import { CompanionSwitcher } from "@/components/companions/CompanionSwitcher";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";

type CompanionContextBarProps = {
  surface: string;
  note?: string;
};

export function CompanionContextBar({ surface, note }: CompanionContextBarProps) {
  const ctx = useActiveCompanionContext();
  const companion = ctx.activeCompanion;

  return (
    <div className="companion-context-shell">
      <section className="companion-context-bar dynamic-glass" aria-label={`${surface} companion context`}>
        <div className="companion-context-copy">
          <div className="companion-context-icon" aria-hidden="true">
            <HeartHandshake size={16} strokeWidth={1.8} />
          </div>
          <div>
            <div className="companion-context-eyebrow">{surface} companion context</div>
            <h2>{ctx.allCompanions ? "All Companions" : companion?.name ?? "Echora"}</h2>
            <p>
              {ctx.allCompanions
                ? "Showing all companion scopes"
                : companion?.relationship_role || companion?.current_mode || "Long-term companion context"}
              {note ? ` / ${note}` : ""}
            </p>
          </div>
        </div>
        <div className="companion-context-actions">
          <CompanionSwitcher />
          {companion && !ctx.allCompanions && (
            <Link className="glass-btn glass-btn-secondary companion-context-link" href={`/companions/${companion.id}`}>
              Profile
            </Link>
          )}
        </div>
      </section>
    </div>
  );
}
