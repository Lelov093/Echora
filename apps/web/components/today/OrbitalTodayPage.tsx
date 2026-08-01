"use client";

import Link from "next/link";
import Image from "next/image";
import {
  ArrowRight,
  BookOpen,
  Clock3,
  Database,
  MessageCircle,
  Radio,
  ShieldCheck,
} from "lucide-react";
import { DataState } from "@/components/patterns/DataState";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";
import { useCompanionHubOverview } from "@/lib/hooks/useCompanionHubOverview";

function readText(value: unknown, fallback: string) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function recordText(record: Record<string, unknown>, keys: string[], fallback: string) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return fallback;
}

export function OrbitalTodayPage() {
  const companionContext = useActiveCompanionContext();
  const hub = useCompanionHubOverview(companionContext.activeCompanionId);

  if (hub.loading) {
    return (
      <main className="orbital-home-page">
        <DataState kind="loading" title="Preparing Today" description="Loading continuity, review queues, and recent Companion context." />
      </main>
    );
  }

  if (hub.error || !hub.data) {
    return (
      <main className="orbital-home-page">
        <DataState
          kind="error"
          title="Today is unavailable"
          description={hub.error || "The Companion workspace did not return a readable response."}
          action={<button type="button" className="orbital-primary-action" onClick={() => void hub.reload()}>Try again</button>}
        />
      </main>
    );
  }

  const companionName = companionContext.activeCompanion?.name || readText(hub.data.companion.name, "Companion");
  const role = companionContext.activeCompanion?.relationship_role
    || companionContext.activeCompanion?.subtitle
    || "Long-term companion";
  const mode = readText(hub.data.companion.current_mode, "project");
  const continuity = hub.data.continuity;
  const topic = continuity?.current_topic || continuity?.current_goal || "Start a new thread together.";
  const summary = continuity?.last_assistant_summary
    || continuity?.last_user_intent
    || "Your current Companion context is ready without crossing memory boundaries.";
  const nextStep = continuity?.suggested_next_steps?.[0];
  const nextStepLabel = nextStep
    ? recordText(nextStep, ["title", "label", "summary", "action"], "Continue the current thread")
    : "Continue the current thread";
  const pendingMemory = Number(hub.data.stats.pending_memory_candidates || 0);
  const queuedPresence = Number(hub.data.stats.queued_presence_opportunities || 0);
  const activeMemories = Number(hub.data.stats.active_memories || 0);
  const recentMemories = hub.data.recentMemories.slice(0, 3);
  const presenceItems = hub.data.presencePreview.slice(0, 2);
  const conversationHref = continuity?.conversation_id
    ? `/conversation?conversation=${encodeURIComponent(continuity.conversation_id)}`
    : "/conversation";

  return (
    <main className="orbital-home-page orbital-today">
      <header className="orbital-page-heading">
        <span>Companion Space</span>
        <h1>Today</h1>
        <p>Here&apos;s what matters now for {companionName}.</p>
      </header>

      <section className="orbital-continue-card">
        <div className="orbital-section-kicker">Continue where you left off</div>
        <div className="orbital-continue-main">
          <div className="orbital-companion-emblem" aria-hidden="true">
            <Image src="/assets/echora-orb.png" alt="" width={68} height={68} />
          </div>
          <div className="orbital-continue-copy">
            <small>{role}</small>
            <h2>Continue with {companionName}</h2>
            <strong>{topic}</strong>
            <p>{summary}</p>
            <div className="orbital-inline-meta">
              <span><Clock3 size={14} /> Latest continuity</span>
              <span>{mode} mode</span>
              <span><ShieldCheck size={14} /> Private by default</span>
            </div>
          </div>
          <Link className="orbital-primary-action" href={conversationHref}>
            Open conversation <ArrowRight size={17} />
          </Link>
        </div>
        <Link className="orbital-next-action" href={conversationHref}>
          <span><BookOpen size={17} /> Next action</span>
          <strong>{nextStepLabel}</strong>
          <small>Companion-scoped</small>
          <ArrowRight size={16} />
        </Link>
      </section>

      <div className="orbital-today-grid">
        <section className="orbital-home-panel orbital-review-panel">
          <div className="orbital-home-panel-title">
            <div>
              <span>Decisions</span>
              <h2>Review queue</h2>
            </div>
            <Link href="/memory">Open all <ArrowRight size={14} /></Link>
          </div>

          <Link className="orbital-queue-summary" href="/memory">
            <Database size={19} />
            <span><strong>Memory candidates</strong><small>Nothing commits without review.</small></span>
            <b>{pendingMemory}</b>
          </Link>
          {recentMemories.map((memory, index) => (
            <Link className="orbital-queue-item" href="/memory" key={String(memory.id || index)}>
              <BookOpen size={16} />
              <span>
                <strong>{recordText(memory, ["summary", "content"], "Committed Companion memory")}</strong>
                <small>{recordText(memory, ["state", "type"], "private memory")}</small>
              </span>
              <ArrowRight size={14} />
            </Link>
          ))}
          {recentMemories.length === 0 ? (
            <div className="orbital-home-empty">No recent committed memories for this Companion.</div>
          ) : null}
        </section>

        <section className="orbital-home-panel">
          <div className="orbital-home-panel-title">
            <div>
              <span>Quiet support</span>
              <h2>Presence</h2>
            </div>
            <Link href="/presence">View queue <ArrowRight size={14} /></Link>
          </div>
          <div className="orbital-panel-metric">
            <Radio size={20} />
            <strong>{queuedPresence}</strong>
            <span>queued opportunities</span>
          </div>
          {presenceItems.map((item, index) => (
            <Link className="orbital-queue-item" href="/presence" key={String(item.id || index)}>
              <MessageCircle size={16} />
              <span>
                <strong>{recordText(item, ["title", "message"], "Presence opportunity")}</strong>
                <small>{recordText(item, ["reason", "status"], "waiting quietly")}</small>
              </span>
              <ArrowRight size={14} />
            </Link>
          ))}
          {presenceItems.length === 0 ? (
            <div className="orbital-home-empty">No interruption is scheduled. Presence remains quiet.</div>
          ) : null}
        </section>

        <section className="orbital-home-panel orbital-relationship-panel">
          <div className="orbital-home-panel-title">
            <div>
              <span>Companion context</span>
              <h2>Relationship</h2>
            </div>
            <Link href="/companions">Open profile <ArrowRight size={14} /></Link>
          </div>
          <Image
            className="orbital-relationship-image"
            src="/assets/relationship-constellation.png"
            alt={`${companionName} relationship constellation`}
            width={720}
            height={420}
          />
          <div className="orbital-relationship-copy">
            <strong>{companionName}</strong>
            <span>{role}</span>
            <p>{activeMemories} committed memories remain inside the active Companion scope.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
