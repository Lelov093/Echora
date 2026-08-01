"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, HeartHandshake, MessageCircle, PencilLine, Save, Sparkles, UserRound } from "lucide-react";
import { companionProfilesApi } from "@/lib/api/companionProfiles";

type ProfileRecord = Record<string, unknown>;
type PreferenceKey = "response_length" | "guidance_style" | "correction_style" | "humor_style" | "conflict_style";

type OwnerProfileDraft = {
  display_name: string;
  user_preferred_name: string;
  identity_summary: string;
  origin_story: string;
  self_continuity_summary: string;
  core_traits_text: string;
  identity_labels_text: string;
  persona_summary: string;
  communication_style_summary: string;
  tone_descriptors_text: string;
  core_values_text: string;
  response_length: string;
  guidance_style: string;
  correction_style: string;
  humor_style: string;
  conflict_style: string;
  relationship_role: string;
  contract_summary: string;
  collaboration_style_summary: string;
  support_scope_text: string;
};

type ProfileVersions = {
  identity: unknown;
  persona: unknown;
  contract: unknown;
  boundary: unknown;
};

type StoredProfileDraft = {
  version: 1;
  companion_id: string;
  saved_at: string;
  draft: OwnerProfileDraft;
  base_versions: ProfileVersions;
};

const DRAFT_VERSION = 1;
const preferenceLabels: Record<PreferenceKey, Record<string, string>> = {
  response_length: { concise: "简洁为主", balanced: "自然平衡", detailed: "充分展开" },
  guidance_style: { listen_first: "先倾听理解", ask_then_advise: "先确认再建议", direct_help: "直接提供帮助" },
  correction_style: { gentle: "温和提醒", direct: "清楚直接", collaborative: "一起核对" },
  humor_style: { restrained: "克制使用", natural: "自然流露", playful: "更活泼一些" },
  conflict_style: { calm_clarify: "先澄清误会", direct_discuss: "坦诚讨论", give_space: "先留出空间" },
};

export function CompanionOwnerProfile({
  companionId,
  identity,
  persona,
  contract,
  boundary,
}: {
  companionId: string;
  identity: ProfileRecord;
  persona: ProfileRecord;
  contract: ProfileRecord;
  boundary: ProfileRecord;
}) {
  const currentDraft = useMemo(
    () => buildDraft(identity, persona, contract),
    [identity, persona, contract],
  );
  const currentVersions = useMemo(
    () => ({
      identity: identity.updated_at,
      persona: persona.updated_at,
      contract: contract.updated_at,
      boundary: boundary.updated_at,
    }),
    [identity.updated_at, persona.updated_at, contract.updated_at, boundary.updated_at],
  );
  const storageKey = `echora:companion-profile-draft:v${DRAFT_VERSION}:${companionId}`;
  const [editing, setEditing] = useState(false);
  const [draftReady, setDraftReady] = useState(false);
  const [draft, setDraft] = useState<OwnerProfileDraft>(currentDraft);
  const [baseVersions, setBaseVersions] = useState<ProfileVersions>(currentVersions);
  const [restoredAt, setRestoredAt] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const client = useQueryClient();

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      try {
        const raw = window.localStorage.getItem(storageKey);
        if (raw) {
          const stored = JSON.parse(raw) as StoredProfileDraft;
          if (
            stored.version === DRAFT_VERSION
            && stored.companion_id === companionId
            && stored.draft
            && stored.base_versions
          ) {
            setDraft((current) => ({ ...current, ...stored.draft }));
            setBaseVersions(stored.base_versions);
            setRestoredAt(stored.saved_at);
            setEditing(true);
          }
        }
      } catch {
        window.localStorage.removeItem(storageKey);
      } finally {
        setDraftReady(true);
      }
    });
    return () => { cancelled = true; };
  }, [companionId, storageKey]);

  useEffect(() => {
    if (!draftReady || !editing) return;
    const stored: StoredProfileDraft = {
      version: DRAFT_VERSION,
      companion_id: companionId,
      saved_at: new Date().toISOString(),
      draft,
      base_versions: baseVersions,
    };
    window.localStorage.setItem(storageKey, JSON.stringify(stored));
  }, [baseVersions, companionId, draft, draftReady, editing, storageKey]);

  const save = useMutation({
    mutationFn: () => companionProfilesApi.patchOwnerSettings(companionId, {
      display_name: draft.display_name.trim(),
      user_preferred_name: draft.user_preferred_name.trim(),
      identity_summary: draft.identity_summary.trim(),
      origin_story: draft.origin_story.trim(),
      self_continuity_summary: draft.self_continuity_summary.trim(),
      core_traits_json: splitList(draft.core_traits_text),
      identity_labels_json: splitList(draft.identity_labels_text),
      persona_summary: draft.persona_summary.trim(),
      communication_style_summary: draft.communication_style_summary.trim(),
      tone_descriptors_json: splitList(draft.tone_descriptors_text),
      core_values_json: splitList(draft.core_values_text),
      response_preferences_json: {
        response_length: draft.response_length,
        guidance_style: draft.guidance_style,
        correction_style: draft.correction_style,
        humor_style: draft.humor_style,
        conflict_style: draft.conflict_style,
      },
      relationship_role: draft.relationship_role,
      contract_summary: draft.contract_summary.trim(),
      collaboration_style_summary: draft.collaboration_style_summary.trim(),
      support_scope_json: splitList(draft.support_scope_text),
      expected_identity_updated_at: baseVersions.identity,
      expected_persona_updated_at: baseVersions.persona,
      expected_contract_updated_at: baseVersions.contract,
      expected_boundary_updated_at: baseVersions.boundary,
    }),
    onSuccess: async () => {
      window.localStorage.removeItem(storageKey);
      await Promise.all(["identity", "persona", "contract", "boundary"].map((kind) =>
        client.invalidateQueries({ queryKey: ["companions", companionId, kind] }),
      ));
      await Promise.all([
        client.invalidateQueries({ queryKey: ["companions", companionId, "workspace"] }),
        client.invalidateQueries({ queryKey: ["companions", companionId, "chronicle"] }),
        client.invalidateQueries({ queryKey: ["companions"] }),
      ]);
      setEditing(false);
      setRestoredAt(null);
      setConfirmDiscard(false);
    },
  });

  const isDirty = JSON.stringify(draft) !== JSON.stringify(currentDraft);
  const baseChanged = JSON.stringify(baseVersions) !== JSON.stringify(currentVersions);

  const beginEditing = () => {
    setDraft(currentDraft);
    setBaseVersions(currentVersions);
    setRestoredAt(null);
    setConfirmDiscard(false);
    save.reset();
    setEditing(true);
  };
  const discard = () => {
    window.localStorage.removeItem(storageKey);
    setDraft(currentDraft);
    setBaseVersions(currentVersions);
    setRestoredAt(null);
    setConfirmDiscard(false);
    setEditing(false);
    save.reset();
  };
  const requestCancel = () => {
    if (isDirty || restoredAt) setConfirmDiscard(true);
    else discard();
  };
  const update = <K extends keyof OwnerProfileDraft>(field: K, value: OwnerProfileDraft[K]) => {
    setDraft((current) => ({ ...current, [field]: value }));
    setConfirmDiscard(false);
    save.reset();
  };

  return (
    <article className={`profile-section profile-owner-settings ${editing ? "is-editing" : ""}`}>
      <header className="profile-owner-heading">
        <div>
          <small>伙伴个人档案</small>
          <h2>{editing ? "一起塑造这位伙伴" : "认识这位伙伴"}</h2>
          <p>这些设置会进入当前伙伴的真实 Agent 上下文，影响身份、人格、相处方式与回复偏好；不同伙伴始终独立。</p>
        </div>
        {!editing ? <button type="button" className="profile-action" onClick={beginEditing}><PencilLine size={15} />编辑档案</button> : null}
      </header>

      {editing ? (
        <>
          {restoredAt ? <div className="profile-draft-notice" role="status"><Save size={16} /><span><strong>已恢复未保存草稿</strong>刷新页面不会丢失当前编辑；只有点击保存后才会影响伙伴。</span></div> : null}
          {baseChanged ? <div className="profile-draft-notice is-warning" role="alert"><span><strong>正式档案在草稿建立后发生过变化</strong>你仍可继续查看草稿，但保存时会进行版本校验，避免静默覆盖。</span></div> : null}
          <div className="owner-settings-editor">
            <ProfileEditGroup icon={UserRound} title="身份与关系" description="定义伙伴是谁、如何称呼你，以及你们希望建立怎样的长期关系。">
              <Field label="伙伴名字"><input required maxLength={80} value={draft.display_name} onChange={(event) => update("display_name", event.target.value)} /></Field>
              <Field label="伙伴如何称呼你"><input maxLength={80} value={draft.user_preferred_name} onChange={(event) => update("user_preferred_name", event.target.value)} /></Field>
              <Field label="身份表达" wide description="伙伴如何理解和介绍自己。"><textarea rows={3} maxLength={1000} value={draft.identity_summary} onChange={(event) => update("identity_summary", event.target.value)} /></Field>
              <Field label="关系定位"><select value={draft.relationship_role} onChange={(event) => update("relationship_role", event.target.value)}><option value="companion">长期伙伴</option><option value="collaborator">协作搭档</option><option value="mentor">学习伙伴</option><option value="observer">安静观察者</option></select></Field>
              <Field label="关系约定" wide description="双方希望长期遵守的相处原则。"><textarea rows={3} maxLength={1000} value={draft.contract_summary} onChange={(event) => update("contract_summary", event.target.value)} /></Field>
            </ProfileEditGroup>

            <ProfileEditGroup icon={Sparkles} title="人格与价值观" description="这些内容形成稳定人格基线；成长建议不能未经确认覆盖它们。">
              <Field label="人格概述" wide><textarea rows={4} maxLength={1600} value={draft.persona_summary} onChange={(event) => update("persona_summary", event.target.value)} /></Field>
              <Field label="核心性格" description="每行或用逗号分隔，最多 8 项。"><textarea rows={4} maxLength={700} value={draft.core_traits_text} onChange={(event) => update("core_traits_text", event.target.value)} /></Field>
              <Field label="核心价值观" description="例如真诚、好奇、克制、独立思考。"><textarea rows={4} maxLength={700} value={draft.core_values_text} onChange={(event) => update("core_values_text", event.target.value)} /></Field>
              <Field label="情绪与语气特征" description="例如温暖、沉静、活泼、坦率。"><textarea rows={3} maxLength={700} value={draft.tone_descriptors_text} onChange={(event) => update("tone_descriptors_text", event.target.value)} /></Field>
              <Field label="身份标签" description="用于保持自我定位，不等同于工具或权限。"><textarea rows={3} maxLength={700} value={draft.identity_labels_text} onChange={(event) => update("identity_labels_text", event.target.value)} /></Field>
            </ProfileEditGroup>

            <ProfileEditGroup icon={MessageCircle} title="沟通与相处方式" description="决定伙伴在日常对话、建议、纠错和分歧中如何回应你。">
              <Field label="沟通方式" wide><textarea rows={3} maxLength={1000} value={draft.communication_style_summary} onChange={(event) => update("communication_style_summary", event.target.value)} /></Field>
              <Field label="回复详略"><PreferenceSelect value={draft.response_length} kind="response_length" onChange={(value) => update("response_length", value)} /></Field>
              <Field label="提供帮助的方式"><PreferenceSelect value={draft.guidance_style} kind="guidance_style" onChange={(value) => update("guidance_style", value)} /></Field>
              <Field label="指出错误的方式"><PreferenceSelect value={draft.correction_style} kind="correction_style" onChange={(value) => update("correction_style", value)} /></Field>
              <Field label="幽默与玩笑"><PreferenceSelect value={draft.humor_style} kind="humor_style" onChange={(value) => update("humor_style", value)} /></Field>
              <Field label="面对分歧"><PreferenceSelect value={draft.conflict_style} kind="conflict_style" onChange={(value) => update("conflict_style", value)} /></Field>
              <Field label="协作方式" wide><textarea rows={3} maxLength={1200} value={draft.collaboration_style_summary} onChange={(event) => update("collaboration_style_summary", event.target.value)} /></Field>
              <Field label="希望伙伴支持的范围" wide description="每行或用逗号分隔，例如日常陪伴、计划梳理、学习支持。"><textarea rows={3} maxLength={700} value={draft.support_scope_text} onChange={(event) => update("support_scope_text", event.target.value)} /></Field>
            </ProfileEditGroup>

            <ProfileEditGroup icon={HeartHandshake} title="共同设定与连续性" description="为长期相处提供稳定背景，但不伪装成现实世界事实。">
              <Field label="共同设定或相识背景" wide><textarea rows={4} maxLength={2000} value={draft.origin_story} onChange={(event) => update("origin_story", event.target.value)} /></Field>
              <Field label="希望长期保持的自我连续性" wide><textarea rows={3} maxLength={1200} value={draft.self_continuity_summary} onChange={(event) => update("self_continuity_summary", event.target.value)} /></Field>
            </ProfileEditGroup>
          </div>
          <footer className={`profile-save-bar ${isDirty ? "has-draft" : ""}`}>
            <div>
              <strong>{isDirty ? "草稿已在这台设备暂存" : "当前没有新的修改"}</strong>
              <span>正式保存后，从伙伴的下一次 Agent 回复开始使用新档案。</span>
            </div>
            <div>
              <button type="button" className="is-primary" disabled={!draft.display_name.trim() || !isDirty || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "正在保存…" : <><Check size={15} />保存伙伴档案</>}</button>
              <button type="button" disabled={save.isPending} onClick={requestCancel}>取消编辑</button>
            </div>
            {save.isError ? <p role="alert">保存失败。正式档案可能已变化，当前草稿仍然保留；刷新后可继续处理。</p> : null}
            {confirmDiscard ? <div className="profile-discard-confirm" role="alert"><span>确定放弃这份未保存草稿吗？</span><button type="button" onClick={discard}>放弃草稿</button><button type="button" onClick={() => setConfirmDiscard(false)}>继续编辑</button></div> : null}
          </footer>
        </>
      ) : (
        <ProfileDisplay draft={currentDraft} />
      )}
    </article>
  );
}

function ProfileDisplay({ draft }: { draft: OwnerProfileDraft }) {
  return (
    <div className="profile-display">
      <DisplayGroup title="身份与关系" icon={UserRound}>
        <DisplayValue label="伙伴名字" value={draft.display_name} />
        <DisplayValue label="对你的称呼" value={draft.user_preferred_name} />
        <DisplayValue label="身份表达" value={draft.identity_summary} wide />
        <DisplayValue label="关系定位" value={relationshipLabel(draft.relationship_role)} />
        <DisplayValue label="关系约定" value={draft.contract_summary} wide />
      </DisplayGroup>
      <DisplayGroup title="人格与价值观" icon={Sparkles}>
        <DisplayValue label="人格概述" value={draft.persona_summary} wide />
        <DisplayTags label="核心性格" value={draft.core_traits_text} />
        <DisplayTags label="核心价值观" value={draft.core_values_text} />
        <DisplayTags label="表达特征" value={draft.tone_descriptors_text} />
      </DisplayGroup>
      <DisplayGroup title="沟通与相处方式" icon={MessageCircle}>
        <DisplayValue label="沟通方式" value={draft.communication_style_summary} wide />
        <DisplayValue label="回复详略" value={preferenceLabels.response_length[draft.response_length]} />
        <DisplayValue label="提供帮助" value={preferenceLabels.guidance_style[draft.guidance_style]} />
        <DisplayValue label="指出错误" value={preferenceLabels.correction_style[draft.correction_style]} />
        <DisplayValue label="面对分歧" value={preferenceLabels.conflict_style[draft.conflict_style]} />
        <DisplayValue label="协作方式" value={draft.collaboration_style_summary} wide />
        <DisplayTags label="支持范围" value={draft.support_scope_text} />
      </DisplayGroup>
      <DisplayGroup title="共同设定与连续性" icon={HeartHandshake}>
        <DisplayValue label="共同设定" value={draft.origin_story} wide />
        <DisplayValue label="长期保持的自我连续性" value={draft.self_continuity_summary} wide />
      </DisplayGroup>
    </div>
  );
}

function ProfileEditGroup({ icon: Icon, title, description, children }: { icon: typeof UserRound; title: string; description: string; children: React.ReactNode }) {
  return <section className="profile-edit-group"><header><Icon size={18} aria-hidden="true" /><span><strong>{title}</strong><small>{description}</small></span></header><div>{children}</div></section>;
}
function Field({ label, description, wide = false, children }: { label: string; description?: string; wide?: boolean; children: React.ReactNode }) {
  return <label className={wide ? "is-wide" : ""}><span>{label}</span>{children}{description ? <small>{description}</small> : null}</label>;
}
function PreferenceSelect({ value, kind, onChange }: { value: string; kind: PreferenceKey; onChange: (value: string) => void }) {
  return <select value={value} onChange={(event) => onChange(event.target.value)}>{Object.entries(preferenceLabels[kind]).map(([option, label]) => <option key={option} value={option}>{label}</option>)}</select>;
}
function DisplayGroup({ icon: Icon, title, children }: { icon: typeof UserRound; title: string; children: React.ReactNode }) {
  return <section className="profile-display-group"><header><Icon size={17} aria-hidden="true" /><h3>{title}</h3></header><div>{children}</div></section>;
}
function DisplayValue({ label, value, wide = false }: { label: string; value?: string; wide?: boolean }) {
  return <div className={`profile-display-value ${wide ? "is-wide" : ""}`}><small>{label}</small><p className={value ? "" : "is-empty"}>{value || "尚未设置"}</p></div>;
}
function DisplayTags({ label, value }: { label: string; value: string }) {
  const items = splitList(value);
  return <div className="profile-display-value is-wide"><small>{label}</small>{items.length ? <div className="profile-tag-list">{items.map((item) => <span key={item}>{item}</span>)}</div> : <p className="is-empty">尚未设置</p>}</div>;
}

function buildDraft(identity: ProfileRecord, persona: ProfileRecord, contract: ProfileRecord): OwnerProfileDraft {
  const contractJson = record(contract.contract_json);
  const preferences = record(persona.response_preferences_json);
  return {
    display_name: String(identity.display_name || ""),
    user_preferred_name: String(contractJson.user_preferred_name || ""),
    identity_summary: String(identity.identity_summary || ""),
    origin_story: String(identity.origin_story || ""),
    self_continuity_summary: String(identity.self_continuity_summary || ""),
    core_traits_text: joinList(identity.core_traits_json),
    identity_labels_text: joinList(identity.identity_labels_json),
    persona_summary: String(persona.persona_summary || ""),
    communication_style_summary: String(persona.communication_style_summary || ""),
    tone_descriptors_text: joinList(persona.tone_descriptors_json),
    core_values_text: joinList(persona.core_values_json),
    response_length: String(preferences.response_length || "balanced"),
    guidance_style: String(preferences.guidance_style || "listen_first"),
    correction_style: String(preferences.correction_style || "collaborative"),
    humor_style: String(preferences.humor_style || "natural"),
    conflict_style: String(preferences.conflict_style || "calm_clarify"),
    relationship_role: String(contract.relationship_role || "companion"),
    contract_summary: String(contract.contract_summary || ""),
    collaboration_style_summary: String(contract.collaboration_style_summary || ""),
    support_scope_text: joinList(contract.support_scope_json),
  };
}
function splitList(value: string): string[] {
  return [...new Set(value.split(/[\n,，、;；]+/).map((item) => item.trim()).filter(Boolean))].slice(0, 8);
}
function joinList(value: unknown): string {
  return Array.isArray(value) ? value.map((item) => typeof item === "string" ? item : String(record(item).label || record(item).name || "")).filter(Boolean).join("\n") : "";
}
function record(value: unknown): ProfileRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as ProfileRecord : {};
}
function relationshipLabel(value: string) {
  return ({ companion: "长期伙伴", collaborator: "协作搭档", mentor: "学习伙伴", observer: "安静观察者" } as Record<string, string>)[value] || value;
}
