"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArrowRight, MessageCircle, PencilLine, Plus, RotateCcw, Search, ShieldCheck } from "lucide-react";
import { CompanionOrb } from "@/components/companion/CompanionOrb";
import { CompanionCreatePanel } from "@/components/companions/CompanionCreatePanel";
import { companionProfilesApi } from "@/lib/api/companionProfiles";
import { companionWorkspaceApi } from "@/lib/api/companionWorkspace";
import { createCompanion, getCompanion } from "@/lib/api/companions";
import { createConversation, listConversations } from "@/lib/api/conversations";
import { companionKeys, useCompanionWorkspaceQuery } from "@/lib/queries/companions";
import type { CompanionBundle, PaginatedItems } from "@/lib/types";
import { HomePagination } from "./HomePagination";

type SingleCompanionHomeProps = {
  activeCompanions: CompanionBundle[];
  archivedCompanions: CompanionBundle[];
  activePagination: PaginatedItems<CompanionBundle>["pagination"];
  archivedPagination: PaginatedItems<CompanionBundle>["pagination"];
  selectedCompanionId?: string;
  singleQuery: string;
};

type OwnerDraft = {
  display_name: string;
  identity_summary: string;
  communication_style_summary: string;
  relationship_role: string;
  contract_summary: string;
  user_preferred_name: string;
};

const emptyDraft: OwnerDraft = {
  display_name: "",
  identity_summary: "",
  communication_style_summary: "",
  relationship_role: "companion",
  contract_summary: "",
  user_preferred_name: "",
};

export function SingleCompanionHome({ activeCompanions, archivedCompanions, activePagination, archivedPagination, selectedCompanionId, singleQuery }: SingleCompanionHomeProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const allCompanions = useMemo(
    () => [...activeCompanions, ...archivedCompanions],
    [activeCompanions, archivedCompanions],
  );
  const [selectedId, setSelectedId] = useState(() => allCompanions.some((item) => item.id === selectedCompanionId) ? selectedCompanionId ?? "" : allCompanions[0]?.id ?? "");
  const [creating, setCreating] = useState(false);

  const selectedOnPage = allCompanions.find((item) => item.id === selectedId) ?? null;
  const selectedQuery = useQuery({
    queryKey: ["companions", selectedId, "home-selection"],
    queryFn: () => getCompanion(selectedId),
    enabled: Boolean(selectedId && !selectedOnPage),
  });
  const selectedCandidate = selectedOnPage ?? selectedQuery.data ?? null;
  const selected = selectedCandidate?.companion_environment === "product" && ["active", "archived"].includes(selectedCandidate.identity_profile_status ?? "active")
    ? selectedCandidate
    : null;
  const invalidRequestedCompanion = Boolean(selectedId && (selectedQuery.isError || (selectedCandidate && !selected)));
  const replaceSearch = (updates: Record<string, string | number | null>) => {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, String(value));
    }
    router.replace(`/?${next.toString()}`, { scroll: false });
  };
  const selectCompanion = (id: string) => {
    setSelectedId(id);
    replaceSearch({ mode: "single", companion_id: id });
  };
  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    const nextQuery = String(new FormData(event.currentTarget as HTMLFormElement).get("single_q") ?? "").trim();
    replaceSearch({ single_q: nextQuery || null, active_page: 1, archived_page: 1 });
  };

  return (
    <div className="companion-home-workspace single-home-workspace">
      <aside className="companion-home-index" aria-label="伙伴列表">
        <div className="companion-home-index-heading">
          <div><small>我的伙伴</small><strong>{activePagination.total} 位正在相处</strong></div>
          <button type="button" onClick={() => setCreating(true)} aria-label="创建伙伴"><Plus size={19} /></button>
        </div>
        <form className="companion-home-search" role="search" onSubmit={submitSearch}>
          <Search size={17} aria-hidden="true" />
          <label className="sr-only" htmlFor="home-companion-search">搜索伙伴</label>
          <input key={singleQuery} id="home-companion-search" name="single_q" defaultValue={singleQuery} placeholder="搜索伙伴" />
          <button type="submit">搜索</button>
        </form>
        <div className="companion-home-list">
          <CompanionListSection
            label="共同生活中"
            companions={activeCompanions}
            selectedId={selected?.id ?? ""}
            onSelect={selectCompanion}
          />
          <HomePagination label="共同生活中的伙伴" page={activePagination.page} totalPages={activePagination.total_pages} total={activePagination.total} onPageChange={(page) => replaceSearch({ active_page: page })} />
          {archivedCompanions.length > 0 ? (
            <CompanionListSection
              label="已归档"
              companions={archivedCompanions}
              selectedId={selected?.id ?? ""}
              onSelect={selectCompanion}
              archived
            />
          ) : null}
          <HomePagination label="已归档伙伴" page={archivedPagination.page} totalPages={archivedPagination.total_pages} total={archivedPagination.total} onPageChange={(page) => replaceSearch({ archived_page: page })} />
          {activeCompanions.length === 0 && archivedCompanions.length === 0 ? (
            <p className="companion-home-list-empty">没有找到匹配的伙伴。</p>
          ) : null}
        </div>
        <footer><ShieldCheck size={15} /> 每位伙伴的记忆、关系与边界保持独立。</footer>
      </aside>
      <section className="companion-home-detail">
        {invalidRequestedCompanion ? (
          <InvalidCompanionSelection />
        ) : selected ? (
          <SingleCompanionDetail key={selected.id} companion={selected} archived={selected.identity_profile_status === "archived"} />
        ) : (
          <EmptySingleHome onCreate={() => setCreating(true)} archivedCount={archivedPagination.total} />
        )}
      </section>
      {creating ? (
        <div className="companion-create-backdrop" role="presentation">
          <div className="companion-create-dialog" role="dialog" aria-modal="true" aria-label="认识一位新伙伴">
            <CreateCompanionFlow onClose={() => setCreating(false)} onCreated={(id) => { selectCompanion(id); setCreating(false); }} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SingleCompanionDetail({ companion, archived }: { companion: CompanionBundle; archived: boolean }) {
  const router = useRouter();
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<OwnerDraft>(emptyDraft);
  const [confirmingLifecycle, setConfirmingLifecycle] = useState(false);
  const [lifecycleAccepted, setLifecycleAccepted] = useState(false);

  const identity = useQuery({
    queryKey: ["companions", companion.id, "identity"],
    queryFn: () => companionProfilesApi.identity(companion.id),
  });
  const persona = useQuery({
    queryKey: ["companions", companion.id, "persona"],
    queryFn: () => companionProfilesApi.persona(companion.id),
  });
  const contract = useQuery({
    queryKey: ["companions", companion.id, "contract"],
    queryFn: () => companionProfilesApi.contract(companion.id),
  });
  const boundary = useQuery({
    queryKey: ["companions", companion.id, "boundary"],
    queryFn: () => companionProfilesApi.boundary(companion.id),
  });
  const conversations = useQuery({
    queryKey: ["conversations", companion.id, "active", "home"],
    queryFn: () => listConversations({ companion_id: companion.id, status: "active", page_size: 1 }),
    enabled: !archived,
  });
  const workspace = useCompanionWorkspaceQuery(companion.id);
  const chronicle = useQuery({
    queryKey: ["companions", companion.id, "chronicle", "home"],
    queryFn: () => companionWorkspaceApi.chronicle(companion.id, 30),
  });

  const refreshCompanion = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["companions"] }),
      client.invalidateQueries({ queryKey: companionKeys.workspace(companion.id) }),
      ...["identity", "persona", "contract", "boundary"].map((kind) =>
        client.invalidateQueries({ queryKey: ["companions", companion.id, kind] }),
      ),
    ]);
  };

  const save = useMutation({
    mutationFn: () => companionProfilesApi.patchOwnerSettings(companion.id, {
      ...draft,
      expected_identity_updated_at: identity.data?.updated_at,
      expected_persona_updated_at: persona.data?.updated_at,
      expected_contract_updated_at: contract.data?.updated_at,
      expected_boundary_updated_at: boundary.data?.updated_at,
    }),
    onSuccess: async () => { await refreshCompanion(); setEditing(false); },
  });
  const lifecycle = useMutation({
    mutationFn: () => (archived ? companionProfilesApi.restore : companionProfilesApi.archive)(companion.id, {
      expected_identity_updated_at: identity.data?.updated_at,
      confirm_preserve_history: lifecycleAccepted,
      confirm_boundaries_and_channels: archived && lifecycleAccepted,
    }),
    onSuccess: async () => { await refreshCompanion(); setConfirmingLifecycle(false); setLifecycleAccepted(false); },
  });
  const newConversation = useMutation({
    mutationFn: () => createConversation({ user_id: companion.user_id, companion_id: companion.id, title: `与 ${companion.name} 的对话` }),
    onSuccess: (conversation) => router.push(`/companions/${companion.id}/conversations/${conversation.id}`),
  });

  const enterConversation = () => {
    const latest = conversations.data?.items[0];
    if (latest) router.push(`/companions/${companion.id}/conversations/${latest.id}`);
    else newConversation.mutate();
  };
  const loadingProfiles = identity.isLoading || persona.isLoading || contract.isLoading || boundary.isLoading;
  const profileError = identity.isError || persona.isError || contract.isError || boundary.isError;

  return (
    <div className="single-companion-detail">
      <div className="single-companion-hero">
        <CompanionOrb name={companion.name} size="large" />
        <div>
          <small>{archived ? "已归档关系" : "PRIVATE COMPANION SPACE"}</small>
          <h2>{companion.name}</h2>
          <p>{text(identity.data?.identity_summary) || companion.subtitle || companion.current_focus || "一段正在被共同写下的长期伙伴关系。"}</p>
          <div className="single-companion-status"><i />{archived ? "历史与共同记忆仍被保留" : statusLabel(companion.current_status)}</div>
        </div>
        <div className="single-companion-primary-actions">
          <button type="button" className="home-primary-action" disabled={archived || conversations.isLoading || newConversation.isPending} onClick={enterConversation}>
            <MessageCircle size={18} />{newConversation.isPending ? "正在打开…" : conversations.data?.items[0] ? "继续对话" : "开始对话"}
          </button>
          {!archived ? <button type="button" className="home-icon-action" onClick={() => newConversation.mutate()} disabled={newConversation.isPending} aria-label="新建对话"><Plus size={18} /></button> : null}
        </div>
      </div>

      <div className="single-companion-body">
        <div className="single-companion-main">
          <section className="single-companion-owner-settings">
          <header>
            <div><small>由你直接决定</small><h3>身份与关系</h3></div>
            {!editing && !archived ? <button type="button" onClick={() => { setDraft(ownerDraftFromProfiles(companion, identity.data, persona.data, contract.data)); setEditing(true); }}><PencilLine size={16} />编辑</button> : null}
          </header>
          {loadingProfiles ? <p className="home-inline-state">正在读取伙伴档案…</p> : profileError ? <p className="home-inline-state is-error">伙伴档案暂时不可用。</p> : editing ? (
            <OwnerSettingsForm draft={draft} setDraft={setDraft} saving={save.isPending} onSave={() => save.mutate()} onCancel={() => setEditing(false)} error={save.isError} />
          ) : (
            <div className="single-companion-summary-grid">
              <SummaryItem label="关系" value={relationshipLabel(text(contract.data?.relationship_role) || companion.relationship_role || "companion")} />
              <SummaryItem label="陪伴节奏" value={presenceLabel(text(persona.data?.presence_style) || "balanced")} />
              <SummaryItem label="沟通方式" value={text(persona.data?.communication_style_summary) || "尚未补充"} wide />
              <SummaryItem label="关系约定" value={text(contract.data?.contract_summary) || "从尊重彼此边界开始相处。"} wide />
            </div>
          )}
          </section>
          <CompanionJourney
            companionId={companion.id}
            companionName={companion.name}
            workspace={workspace.data}
            chronicle={chronicle.data}
            loading={workspace.isLoading || chronicle.isLoading}
            error={workspace.isError || chronicle.isError}
          />
        </div>
        <aside className="single-companion-side">
          <section>
            <small>伙伴空间</small>
            <h3>继续了解彼此</h3>
            <Link href={`/companions/${companion.id}/profile`}>查看完整伙伴档案<ArrowRight size={15} /></Link>
            <Link href={`/settings/companions/${companion.id}/presence`}>管理陪伴节奏<ArrowRight size={15} /></Link>
            <Link href={`/companions/${companion.id}/chronicle`}>打开共同历程<ArrowRight size={15} /></Link>
          </section>
          <section className="single-companion-lifecycle">
            <small>关系生命周期</small>
            <h3>{archived ? "恢复这段关系" : "暂时收起这段关系"}</h3>
            <p>{archived ? "恢复前需要重新确认边界与渠道；旧 Presence 队列不会自动恢复。" : "归档保留对话、记忆和共同历程，并停止主动 Presence 与渠道外发。"}</p>
            {confirmingLifecycle ? (
              <div className="home-confirm-block">
                <label><input type="checkbox" checked={lifecycleAccepted} onChange={(event) => setLifecycleAccepted(event.target.checked)} />{archived ? "我已重新确认边界与渠道状态。" : "我理解归档不会删除关系历史。"}</label>
                <div><button type="button" disabled={!lifecycleAccepted || lifecycle.isPending} onClick={() => lifecycle.mutate()}>{lifecycle.isPending ? "处理中…" : archived ? "确认恢复" : "确认归档"}</button><button type="button" onClick={() => { setConfirmingLifecycle(false); setLifecycleAccepted(false); }}>取消</button></div>
                {lifecycle.isError ? <span role="alert">状态可能已经变化，请刷新后重新确认。</span> : null}
              </div>
            ) : (
              <button type="button" className="home-lifecycle-action" onClick={() => setConfirmingLifecycle(true)}>{archived ? <RotateCcw size={16} /> : <Archive size={16} />}{archived ? "恢复伙伴" : "归档伙伴"}</button>
            )}
          </section>
        </aside>
      </div>
      {newConversation.isError ? <p className="home-action-error" role="alert">无法创建新对话，请确认后端状态后重试。</p> : null}
    </div>
  );
}

function OwnerSettingsForm({ draft, setDraft, saving, onSave, onCancel, error }: {
  draft: OwnerDraft;
  setDraft: (draft: OwnerDraft) => void;
  saving: boolean;
  onSave: () => void;
  onCancel: () => void;
  error: boolean;
}) {
  const field = (key: keyof OwnerDraft, value: string) => setDraft({ ...draft, [key]: value });
  return (
    <div className="home-owner-form">
      <label><span>伙伴名字</span><input maxLength={80} value={draft.display_name} onChange={(event) => field("display_name", event.target.value)} /></label>
      <label><span>关系意图</span><select value={draft.relationship_role} onChange={(event) => field("relationship_role", event.target.value)}><option value="companion">长期伙伴</option><option value="collaborator">协作搭档</option><option value="mentor">学习伙伴</option><option value="observer">安静观察者</option></select></label>
      <label><span>希望伙伴如何称呼你</span><input maxLength={80} value={draft.user_preferred_name} onChange={(event) => field("user_preferred_name", event.target.value)} /></label>
      <label className="is-wide"><span>身份表达</span><textarea rows={3} maxLength={1000} value={draft.identity_summary} onChange={(event) => field("identity_summary", event.target.value)} /></label>
      <label className="is-wide"><span>沟通方式</span><textarea rows={3} maxLength={1000} value={draft.communication_style_summary} onChange={(event) => field("communication_style_summary", event.target.value)} /></label>
      <label className="is-wide"><span>关系约定</span><textarea rows={3} maxLength={1000} value={draft.contract_summary} onChange={(event) => field("contract_summary", event.target.value)} /></label>
      <div className="home-form-actions"><button type="button" className="home-primary-action" disabled={!draft.display_name.trim() || saving} onClick={onSave}>{saving ? "正在保存…" : "保存修改"}</button><button type="button" disabled={saving} onClick={onCancel}>取消</button>{error ? <span role="alert">保存失败；档案可能已变化，请刷新后重试。</span> : null}</div>
    </div>
  );
}

function CompanionListSection({ label, companions, selectedId, onSelect, archived = false }: {
  label: string;
  companions: CompanionBundle[];
  selectedId: string;
  onSelect: (id: string) => void;
  archived?: boolean;
}) {
  if (companions.length === 0) return null;
  return (
    <section>
      <small>{label}</small>
      {companions.map((companion, index) => (
        <button key={companion.id} type="button" className={selectedId === companion.id ? "is-selected" : ""} onClick={() => onSelect(companion.id)}>
          <CompanionOrb name={companion.name} index={index} size="small" />
          <span><strong>{companion.name}</strong><small>{companion.relationship_role ? relationshipLabel(companion.relationship_role) : "长期伙伴"}</small></span>
          <em>{archived ? "已归档" : statusLabel(companion.current_status)}</em>
        </button>
      ))}
    </section>
  );
}

function CreateCompanionFlow({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const client = useQueryClient();
  const create = useMutation({
    mutationFn: createCompanion,
    onSuccess: async (companion) => {
      await Promise.all([
        client.invalidateQueries({ queryKey: companionKeys.roster("product") }),
        client.invalidateQueries({ queryKey: companionKeys.roster("archived") }),
      ]);
      onCreated(companion.id);
    },
  });
  return <CompanionCreatePanel creating={create.isPending} message={create.error instanceof Error ? create.error.message : null} onCreate={(payload) => create.mutateAsync(payload).then(() => undefined)} onCancel={onClose} />;
}

function EmptySingleHome({ onCreate, archivedCount }: { onCreate: () => void; archivedCount: number }) {
  return <div className="companion-home-empty"><CompanionOrb name="Echora" size="large" /><small>FIRST MEETING</small><h2>从认识一位伙伴开始</h2><p>建立一段有边界、可延续、会在长期相处中逐渐成长的伙伴关系。</p><button type="button" className="home-primary-action" onClick={onCreate}><Plus size={18} />认识一位新伙伴</button>{archivedCount > 0 ? <span>另有 {archivedCount} 段关系保存在归档中。</span> : null}</div>;
}

function InvalidCompanionSelection() {
  return <div className="companion-home-empty"><CompanionOrb name="Echora" size="large" /><small>COMPANION SCOPE</small><h2>没有找到这位伙伴</h2><p>该链接可能已过期，或不属于当前用户可见的伙伴范围。Echora 不会自动切换到另一位伙伴。</p><Link className="home-primary-action" href="/?mode=single">重新选择伙伴</Link></div>;
}

function SummaryItem({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return <div className={wide ? "is-wide" : ""}><small>{label}</small><p>{value}</p></div>;
}

function text(value: unknown) { return typeof value === "string" ? value : ""; }
function ownerDraftFromProfiles(companion: CompanionBundle, identity?: Record<string, unknown>, persona?: Record<string, unknown>, contract?: Record<string, unknown>): OwnerDraft {
  return {
    display_name: text(identity?.display_name) || companion.name,
    identity_summary: text(identity?.identity_summary),
    communication_style_summary: text(persona?.communication_style_summary),
    relationship_role: text(contract?.relationship_role) || "companion",
    contract_summary: text(contract?.contract_summary),
    user_preferred_name: text(record(contract?.contract_json).user_preferred_name),
  };
}
function statusLabel(status?: string | null) { return status === "busy" ? "专注中" : status === "active" || status === "online" ? "正在陪伴" : "安静在场"; }
function relationshipLabel(role: string) { return ({ companion: "长期伙伴", collaborator: "协作搭档", mentor: "学习伙伴", observer: "安静观察者" } as Record<string, string>)[role] || role; }
function presenceLabel(style: string) { return ({ quiet: "克制地提醒", balanced: "自然接续", expressive: "更积极表达" } as Record<string, string>)[style] || style; }
function record(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }

function CompanionJourney({
  companionId,
  companionName,
  workspace,
  chronicle,
  loading,
  error,
}: {
  companionId: string;
  companionName: string;
  workspace?: Awaited<ReturnType<typeof companionWorkspaceApi.workspace>>;
  chronicle?: Awaited<ReturnType<typeof companionWorkspaceApi.chronicle>>;
  loading: boolean;
  error: boolean;
}) {
  if (loading) return <section className="single-companion-journey"><p className="home-inline-state">正在接续你们上次停留的地方…</p></section>;
  if (error || !workspace || !chronicle) return <section className="single-companion-journey"><p className="home-inline-state is-error">共同历程暂时无法读取；伙伴档案与对话仍可继续使用。</p></section>;
  const confirmed = chronicle.items.filter((item) => !["pending_review", "candidate", "rejected"].includes(item.review_status ?? "") && item.kind !== "relationship_pending");
  const recentGrowth = confirmed.find((item) => item.kind === "growth");
  const recentMemory = workspace.recent_private_memories[0];
  const nextTopic = workspace.continuity?.current_topic || workspace.continuity?.current_goal;
  const relationship = typeof workspace.relationship?.summary === "string" ? workspace.relationship.summary : workspace.identity.relationship_summary;
  return <section className="single-companion-journey" aria-labelledby={`journey-${companionId}`}>
    <header><div><small>我们的现在</small><h3 id={`journey-${companionId}`}>和 {companionName} 继续走下去</h3></div><Link href={`/companions/${companionId}/chronicle`}>查看完整共同历程<ArrowRight size={15} /></Link></header>
    <div className="single-companion-journey-grid">
      <article><small>上次停留</small><h4>{nextTopic || "等待下一次自然相遇"}</h4><p>{workspace.continuity?.last_assistant_summary || "还没有需要续接的上下文；新的对话会从你们当前的关系开始。"}</p></article>
      <article><small>最近记住</small><h4>{recentMemory?.summary || "共同记忆正在慢慢形成"}</h4><p>{recentMemory ? "这条记忆会按当前强度与边界参与后续互动。" : "你可以在记忆页直接补充、修正或调整伙伴的记忆。"}</p><Link href={`/settings/companions/${companionId}/memory`}>管理伙伴记忆</Link></article>
      <article><small>成长与关系</small><h4>{recentGrowth?.summary || relationship || "从尊重彼此边界开始"}</h4><p>{recentGrowth ? "这是最近一项已经确认的成长变化。" : "新的成长与关系理解在你确认前不会成为共同事实。"}</p><Link href={`/settings/companions/${companionId}/growth`}>查看成长与理解</Link></article>
    </div>
  </section>;
}
