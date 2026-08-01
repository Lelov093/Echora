"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  Ban,
  Bot,
  Cable,
  CheckCircle2,
  ClipboardCheck,
  History,
  MessageSquare,
  RefreshCw,
  Shield,
  XCircle,
} from "lucide-react";
import {
  approveChannelMemoryCandidate,
  rejectChannelMemoryCandidate,
  redactChannelMemoryCandidate,
} from "@/lib/api/channelGateway";
import { ListControls } from "@/components/list/ListControls";
import { ConfirmActionDialog } from "@/components/patterns/ConfirmActionDialog";
import { DataState } from "@/components/patterns/DataState";
import { StatusMessage } from "@/components/patterns/StatusMessage";
import { useChannelGateway } from "@/lib/hooks/useChannelGateway";
import { useClientListControls } from "@/lib/hooks/useClientListControls";
import type {
  ChannelAuditLog,
  ChannelBinding,
  ChannelContinuityHandoff,
  ChannelMemoryCandidate,
  ChannelPresencePolicy,
  ChannelRevokeEvent,
  ChannelTraceEvent,
  DiscordBotIdentityStatus,
} from "@/lib/types";

type View = "overview" | "discord" | "companion" | "memory" | "audit";

interface Props {
  view: View;
  companionId?: string | null;
}

function shortId(value?: string | null) {
  return value ? value.slice(0, 8) : "pending";
}

function statusTone(value?: string | null) {
  if (!value) return "pill-sm";
  if (["active", "ready", "configured", "recorded", "authorized", "approved", "sent"].includes(value)) return "pill-sm pill-accent";
  if (["revoked", "disabled", "missing", "missing_token", "rejected", "suppressed", "failed"].includes(value)) return "pill-sm";
  return "pill-sm";
}

export function ChannelGatewayWorkspace({ view, companionId }: Props) {
  const gateway = useChannelGateway({ companionId: companionId ?? undefined });
  const [selectedBindingId, setSelectedBindingId] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [revokeBinding, setRevokeBinding] = useState<ChannelBinding | null>(null);

  const selectedBinding = useMemo(() => {
    return gateway.bindings.find((binding) => binding.id === selectedBindingId) ?? gateway.bindings[0] ?? null;
  }, [gateway.bindings, selectedBindingId]);

  const scopedMessages = useMemo(() => filterByBinding(gateway.messages, selectedBinding?.id), [gateway.messages, selectedBinding?.id]);
  const scopedDeliveries = useMemo(() => filterByBinding(gateway.deliveries, selectedBinding?.id), [gateway.deliveries, selectedBinding?.id]);
  const scopedCandidates = useMemo(() => filterByBinding(gateway.candidates, selectedBinding?.id), [gateway.candidates, selectedBinding?.id]);
  const scopedPolicies = useMemo(() => filterByBinding(gateway.policies, selectedBinding?.id), [gateway.policies, selectedBinding?.id]);
  const scopedHandoffs = useMemo(() => filterByBinding(gateway.handoffs, selectedBinding?.id), [gateway.handoffs, selectedBinding?.id]);
  const scopedTraces = useMemo(() => filterByBinding(gateway.traces, selectedBinding?.id), [gateway.traces, selectedBinding?.id]);
  const scopedAudits = useMemo(() => filterByBinding(gateway.audits, selectedBinding?.id), [gateway.audits, selectedBinding?.id]);
  const scopedRevokes = useMemo(() => filterByBinding(gateway.revokes, selectedBinding?.id), [gateway.revokes, selectedBinding?.id]);

  const runCandidateAction = async (label: string, task: () => Promise<unknown>) => {
    setActionMsg(`${label}...`);
    try {
      await task();
      await gateway.reload();
      setActionMsg(`${label} recorded`);
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : `${label} failed`);
    }
  };

  if (gateway.loading) {
    return (
      <main className="echora-page orbital-detail-page-body">
        <DataState
          kind="loading"
          title="Loading Channel Gateway"
          description="Reading providers, bindings, messages, memory candidates, and audit trails."
        />
      </main>
    );
  }

  return (
    <main className="echora-page orbital-detail-page-body">
      <section className="dynamic-glass p-6 rounded-[28px] flex justify-between items-center flex-wrap gap-4 mb-4">
        <div>
          <h1 className="text-[1.5rem] font-semibold flex items-center gap-2 orbital-detail-heading">
            <Cable size={20} strokeWidth={1.8} />
            Channel Gateway
          </h1>
          <p className="text-sm mt-1 orbital-detail-copy">
            External channels stay companion-scoped, review-gated, auditable, and revocable.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          <span className="pill-sm">providers {gateway.providers.length}</span>
          <span className="pill-sm">bindings {gateway.bindings.length}</span>
          <span className="pill-sm">candidates {gateway.candidates.length}</span>
          <button className="act-btn act-btn-primary" onClick={() => void gateway.reload()}>
            <RefreshCw size={13} strokeWidth={1.8} />
            Reload
          </button>
        </div>
      </section>

      {gateway.error ? <StatusMessage tone="error" className="glass-soft p-3 mb-4">{gateway.error}</StatusMessage> : null}
      {actionMsg ? <StatusMessage tone={actionMsg.includes("failed") ? "error" : "success"} className="glass-soft p-3 mb-4">{actionMsg}</StatusMessage> : null}

      <div className="grid gap-6 items-start lg:grid-cols-[minmax(420px,0.9fr)_minmax(560px,1.1fr)]">
        <div className="domain-stack">
          {(view === "overview" || view === "companion" || view === "discord") && (
            <>
              <ProviderPanel providers={gateway.providers} />
              <DiscordPanel bots={gateway.discordBots} onTest={(bot) => void gateway.testDiscordBot({ bot_key: bot.bot_key })} />
            </>
          )}
          <BindingPanel
            bindings={gateway.bindings}
            selectedBinding={selectedBinding}
            onSelect={setSelectedBindingId}
            onActivate={(id) => void gateway.activateBinding(id, { reason: "frontend activation" })}
            onDisable={(id) => void gateway.disableBinding(id, { reason: "frontend disable" })}
            onRevoke={(id) => setRevokeBinding(gateway.bindings.find((binding) => binding.id === id) ?? null)}
            saving={gateway.saving}
          />
        </div>

        <div className="domain-stack">
          {(view === "overview" || view === "companion" || view === "memory") && (
            <MemoryPanel candidates={scopedCandidates} onAction={runCandidateAction} />
          )}
          {(view === "overview" || view === "companion") && (
            <PresencePanel policies={scopedPolicies} selectedBinding={selectedBinding} onCreatePolicy={gateway.createPresencePolicy} onEnableCheckin={gateway.enableCheckin} />
          )}
          {(view === "overview" || view === "companion") && (
            <MessagePanel messages={scopedMessages} deliveries={scopedDeliveries} />
          )}
          {(view === "overview" || view === "companion" || view === "audit") && (
            <ContinuityPanel handoffs={scopedHandoffs} />
          )}
          {(view === "overview" || view === "companion" || view === "audit") && (
            <AuditPanel traces={scopedTraces} audits={scopedAudits} revokes={scopedRevokes} />
          )}
        </div>
      </div>

      {revokeBinding ? (
        <ConfirmActionDialog
          title="Revoke channel binding?"
          description="Inbound and outbound access will stop immediately. The revoke remains visible in the audit trail and must be reconfigured before this Companion can use the channel again."
          confirmLabel="Revoke binding"
          busy={gateway.saving}
          onCancel={() => setRevokeBinding(null)}
          onConfirm={async () => {
            setActionMsg("Revoking channel binding...");
            const result = await gateway.applyRevoke(revokeBinding.id, { reason: "user-confirmed frontend channel revoke" });
            setActionMsg(result ? "Channel binding revoked and recorded" : "Channel binding revoke failed");
            if (result) setRevokeBinding(null);
          }}
        />
      ) : null}
    </main>
  );
}

function ProviderPanel({ providers }: { providers: { id: string; provider_key: string; provider_display_name: string; provider_status: string; supports_multi_bot: boolean; is_real_provider: boolean }[] }) {
  return (
    <section className="dynamic-glass domain-panel">
      <PanelTitle icon={<Cable size={16} />} title="Providers" subtitle="Gateway providers are capability surfaces, not generic bot platforms." />
      <ListEmpty items={providers} empty="No channel providers loaded.">
        {(provider) => (
          <div key={provider.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{provider.provider_display_name}</strong>
                <div className="domain-list-sub">{provider.provider_key} / {provider.is_real_provider ? "real provider" : "contract provider"}</div>
              </div>
              <span className={statusTone(provider.provider_status)}>{provider.provider_status}</span>
            </div>
            <p className="domain-card-copy">Multi-bot support: {provider.supports_multi_bot ? "enabled" : "not available"}</p>
          </div>
        )}
      </ListEmpty>
    </section>
  );
}

function DiscordPanel({ bots, onTest }: { bots: DiscordBotIdentityStatus[]; onTest: (bot: DiscordBotIdentityStatus) => void }) {
  return (
    <section className="dynamic-glass domain-panel">
      <PanelTitle icon={<Bot size={16} />} title="Discord Bot Identities" subtitle="Each companion can use an independent Discord bot identity." />
      <ListEmpty items={bots} empty="No Discord bot registry entries detected.">
        {(bot) => (
          <div key={bot.bot_key} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{bot.bot_display_name}</strong>
                <div className="domain-list-sub">{bot.bot_key} / user {bot.bot_user_id || "not verified"}</div>
              </div>
              <span className={statusTone(bot.token_status)}>{bot.token_status}</span>
            </div>
            <div className="flex gap-2 flex-wrap mt-2">
              <span className="pill-sm">enabled {String(bot.enabled)}</span>
              {bot.companion_id && <span className="pill-sm">companion {shortId(bot.companion_id)}</span>}
              <button className="act-btn" onClick={() => onTest(bot)}>
                <ClipboardCheck size={12} strokeWidth={1.8} />
                Test
              </button>
            </div>
          </div>
        )}
      </ListEmpty>
    </section>
  );
}

function BindingPanel({
  bindings,
  selectedBinding,
  onSelect,
  onActivate,
  onDisable,
  onRevoke,
  saving,
}: {
  bindings: ChannelBinding[];
  selectedBinding: ChannelBinding | null;
  onSelect: (id: string) => void;
  onActivate: (id: string) => void;
  onDisable: (id: string) => void;
  onRevoke: (id: string) => void;
  saving: boolean;
}) {
  return (
    <section className="dynamic-glass domain-panel">
      <PanelTitle icon={<Shield size={16} />} title="Companion Bindings" subtitle="Bindings control inbound, outbound, memory, and revoke boundaries." />
      <ListEmpty items={bindings} empty="No channel bindings loaded.">
        {(binding) => (
          <div key={binding.id} className={`glass-soft domain-list-card ${selectedBinding?.id === binding.id ? "orbital-detail-selected-card" : ""}`}>
            <div className="domain-list-head">
              <div>
                <strong>{binding.provider?.provider_display_name || "Channel binding"}</strong>
                <div className="domain-list-sub">binding {shortId(binding.id)} / companion {shortId(binding.companion_id)}</div>
              </div>
              <span className={statusTone(binding.binding_status)}>{binding.binding_status}</span>
            </div>
            <div className="flex gap-2 flex-wrap mt-2">
              <span className="pill-sm">inbound {String(binding.can_receive_inbound)}</span>
              <span className="pill-sm">outbound {String(binding.can_send_outbound)}</span>
              <span className="pill-sm">memory {binding.memory_policy}</span>
              <button className="act-btn" onClick={() => onSelect(binding.id)}>Inspect</button>
              <button className="act-btn" disabled={saving || binding.binding_status === "active"} onClick={() => onActivate(binding.id)}>Activate</button>
              <button className="act-btn" disabled={saving || binding.binding_status === "disabled"} onClick={() => onDisable(binding.id)}>Disable</button>
              <button className="act-btn" disabled={saving || binding.binding_status === "revoked"} onClick={() => onRevoke(binding.id)}>
                <Ban size={12} strokeWidth={1.8} />
                Revoke binding
              </button>
            </div>
          </div>
        )}
      </ListEmpty>
    </section>
  );
}

function MemoryPanel({ candidates, onAction }: { candidates: ChannelMemoryCandidate[]; onAction: (label: string, task: () => Promise<unknown>) => void }) {
  return (
    <section className="dynamic-glass domain-panel">
      <PanelTitle icon={<History size={16} />} title="Channel Memory Candidates" subtitle="External channel memories stay review-gated by default." />
      <ListEmpty items={candidates} empty="No channel memory candidates for this scope.">
        {(candidate) => (
          <div key={candidate.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{candidate.candidate_summary}</strong>
                <div className="domain-list-sub">{candidate.target_memory_scope} / salience {candidate.salience_score.toFixed(2)}</div>
              </div>
              <span className={statusTone(candidate.candidate_status)}>{candidate.candidate_status}</span>
            </div>
            <p className="domain-card-copy">{candidate.suggested_memory_content || "No suggested long-term memory content recorded."}</p>
            <div className="flex gap-2 flex-wrap mt-2">
              <span className="pill-sm">review {String(candidate.requires_user_review)}</span>
              <span className="pill-sm">auto commit {String(candidate.auto_commit_allowed)}</span>
              <button className="act-btn" disabled={candidate.candidate_status !== "pending_review"} onClick={() => onAction("Approve", () => approveChannelMemoryCandidate(candidate.id, { review_notes: "Approved from frontend" }))}>
                <CheckCircle2 size={12} strokeWidth={1.8} />
                Approve
              </button>
              <button className="act-btn" disabled={candidate.candidate_status !== "pending_review"} onClick={() => onAction("Reject", () => rejectChannelMemoryCandidate(candidate.id, { review_notes: "Rejected from frontend" }))}>
                <XCircle size={12} strokeWidth={1.8} />
                Reject
              </button>
              <button className="act-btn" disabled={candidate.candidate_status === "redacted"} onClick={() => onAction("Redact", () => redactChannelMemoryCandidate(candidate.id, { review_notes: "Redacted from frontend" }))}>Redact</button>
            </div>
          </div>
        )}
      </ListEmpty>
    </section>
  );
}

function PresencePanel({
  policies,
  selectedBinding,
  onCreatePolicy,
  onEnableCheckin,
}: {
  policies: ChannelPresencePolicy[];
  selectedBinding: ChannelBinding | null;
  onCreatePolicy: (data: Record<string, unknown>) => Promise<unknown>;
  onEnableCheckin: (policyId: string, data: Record<string, unknown>) => Promise<unknown>;
}) {
  return (
    <section className="dynamic-glass domain-panel">
      <PanelTitle icon={<Activity size={16} />} title="Presence Policy" subtitle="Default is reply-only; low-frequency check-in requires opt-in." />
      <div className="flex gap-2 flex-wrap mb-3">
        <button className="act-btn" disabled={!selectedBinding} onClick={() => selectedBinding && void onCreatePolicy({ channel_binding_id: selectedBinding.id })}>Create policy</button>
      </div>
      <ListEmpty items={policies} empty="No presence policy for this binding.">
        {(policy) => (
          <div key={policy.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{policy.presence_mode}</strong>
                <div className="domain-list-sub">budget {policy.remaining_presence_budget}/{policy.daily_presence_budget}</div>
              </div>
              <span className={statusTone(policy.policy_status)}>{policy.policy_status}</span>
            </div>
            <div className="flex gap-2 flex-wrap mt-2">
              <span className="pill-sm">reply-only {String(policy.reply_only_default)}</span>
              <span className="pill-sm">check-in {String(policy.low_frequency_checkin_enabled)}</span>
              <button className="act-btn" disabled={policy.low_frequency_checkin_enabled || policy.policy_status === "revoked"} onClick={() => void onEnableCheckin(policy.id, { user_opt_in: true, daily_presence_budget: 1, remaining_presence_budget: 1 })}>Enable low-frequency check-in</button>
            </div>
          </div>
        )}
      </ListEmpty>
    </section>
  );
}

function MessagePanel({ messages, deliveries }: { messages: { id: string; message_direction: string; message_status: string; message_summary: string; payload_is_ephemeral: boolean }[]; deliveries: { id: string; delivery_status: string; delivery_summary: string; raw_payload_storage_allowed: boolean }[] }) {
  return (
    <section className="dynamic-glass domain-panel">
      <PanelTitle icon={<MessageSquare size={16} />} title="Message & Delivery Trail" subtitle="Inbound is ephemeral; outbound must pass policy and audit." />
      <div className="grid gap-3 md:grid-cols-2">
        <MiniList title="Messages" items={messages} empty="No messages.">
          {(item) => <TrailLine key={item.id} title={item.message_summary} subtitle={`${item.message_direction} / ${item.message_status}`} badge={item.payload_is_ephemeral ? "ephemeral" : "stored"} />}
        </MiniList>
        <MiniList title="Deliveries" items={deliveries} empty="No deliveries.">
          {(item) => <TrailLine key={item.id} title={item.delivery_summary} subtitle={`delivery / ${item.delivery_status}`} badge={item.raw_payload_storage_allowed ? "raw allowed" : "safe"} />}
        </MiniList>
      </div>
    </section>
  );
}

function ContinuityPanel({ handoffs }: { handoffs: ChannelContinuityHandoff[] }) {
  return (
    <section className="dynamic-glass domain-panel">
      <PanelTitle icon={<ClipboardCheck size={16} />} title="Continuity Handoffs" subtitle="Handoffs use safe summaries, not raw history dumps." />
      <ListEmpty items={handoffs} empty="No continuity handoffs.">
        {(handoff) => (
          <div key={handoff.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{handoff.direction || "handoff"}</strong>
                <div className="domain-list-sub">{handoff.visibility_reason || "summary only"}</div>
              </div>
              <span className={statusTone(handoff.handoff_status || handoff.trace_status)}>{handoff.handoff_status || handoff.trace_status}</span>
            </div>
            <div className="flex gap-2 flex-wrap mt-2">
              <span className="pill-sm">raw history {String(handoff.raw_history_included)}</span>
              <span className="pill-sm">private memory {String(handoff.private_memory_included)}</span>
            </div>
          </div>
        )}
      </ListEmpty>
    </section>
  );
}

function AuditPanel({ traces, audits, revokes }: { traces: ChannelTraceEvent[]; audits: ChannelAuditLog[]; revokes: ChannelRevokeEvent[] }) {
  return (
    <section className="dynamic-glass domain-panel">
      <PanelTitle icon={<Shield size={16} />} title="Trace / Audit / Revoke" subtitle="External channel behavior remains inspectable and reversible." />
      <div className="grid gap-3 md:grid-cols-3">
        <MiniList title="Trace" items={traces} empty="No trace events.">
          {(item) => <TrailLine key={item.id} title={item.trace_summary} subtitle={item.trace_event_type} badge={item.trace_status} />}
        </MiniList>
        <MiniList title="Audit" items={audits} empty="No audit logs.">
          {(item) => <TrailLine key={item.id} title={item.audit_summary} subtitle={item.audit_log_type} badge={shortId(item.channel_trace_event_id)} />}
        </MiniList>
        <MiniList title="Revokes" items={revokes} empty="No revoke events.">
          {(item) => <TrailLine key={item.id} title={item.revoke_reason || "Channel revoke"} subtitle={item.revoke_scope} badge={item.revoke_status} />}
        </MiniList>
      </div>
    </section>
  );
}

function PanelTitle({ icon, title, subtitle }: { icon: ReactNode; title: string; subtitle: string }) {
  return (
    <div className="domain-panel-header">
      <div className="domain-panel-icon">{icon}</div>
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}

function ListEmpty<T>({ items, empty, children }: { items: T[]; empty: string; children: (item: T) => ReactNode }) {
  return <div className="domain-list">{items.length > 0 ? items.map(children) : <div className="domain-inline-empty">{empty}</div>}</div>;
}

function MiniList<T>({ title, items, empty, children }: { title: string; items: T[]; empty: string; children: (item: T) => ReactNode }) {
  const list = useClientListControls<T>({
    items,
    searchText: (item) => JSON.stringify(item),
    status: (item) => {
      const record = item as Record<string, unknown>;
      return String(record.status || record.trace_status || record.revoke_status || record.delivery_status || record.message_status || "all");
    },
    initialPageSize: 6,
  });

  return (
    <div className="glass-soft p-3 rounded-[18px]">
      <div className="text-sm font-semibold mb-2 orbital-detail-heading">{title}</div>
      <ListControls
        label={`${title} controls`}
        query={list.query}
        onQueryChange={list.setQuery}
        status={list.status}
        onStatusChange={list.setStatus}
        statuses={list.statuses}
        page={list.page}
        pageSize={list.pageSize}
        total={list.total}
        onPageChange={list.setPage}
        onPageSizeChange={list.setPageSize}
      />
      <div className="domain-list">{list.pageItems.length > 0 ? list.pageItems.map(children) : <div className="domain-inline-empty">{empty}</div>}</div>
    </div>
  );
}

function TrailLine({ title, subtitle, badge }: { title: string; subtitle: string; badge: string }) {
  return (
    <div className="glass-soft domain-list-card">
      <div className="domain-list-head">
        <div>
          <strong>{title || "Recorded event"}</strong>
          <div className="domain-list-sub">{subtitle}</div>
        </div>
        <span className={statusTone(badge)}>{badge}</span>
      </div>
    </div>
  );
}

function filterByBinding<T extends { channel_binding_id?: string | null }>(items: T[], bindingId?: string | null) {
  return bindingId ? items.filter((item) => item.channel_binding_id === bindingId) : items;
}
