"use client";

import { useRef, useState } from "react";
import { Plus, ShieldCheck, X } from "lucide-react";

type CompanionCreatePanelProps = {
  creating?: boolean;
  message?: string | null;
  onCancel?: () => void;
  onCreate: (payload: Record<string, unknown>) => Promise<void>;
};

export function CompanionCreatePanel({ creating = false, message, onCreate, onCancel }: CompanionCreatePanelProps) {
  const [name, setName] = useState("");
  const [userName, setUserName] = useState("");
  const [context, setContext] = useState("");
  const [communicationStyle, setCommunicationStyle] = useState("温和、坦诚、不过度讨好");
  const [relationshipRole, setRelationshipRole] = useState("companion");
  const [presenceStyle, setPresenceStyle] = useState("quiet");
  const [quietStart, setQuietStart] = useState("23:00");
  const [quietEnd, setQuietEnd] = useState("08:00");
  const submittingRef = useRef(false);
  const [submitting, setSubmitting] = useState(false);

  const canCreate = name.trim().length > 0 && !creating && !submitting;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canCreate || submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    const trimmedName = name.trim();
    try {
      await onCreate({
      companion_environment: "product",
      provenance: "user_created",
      name: trimmedName,
      identity: {
        display_name: trimmedName,
        identity_summary: `${trimmedName} 是一位长期存在、保持自我连续性的 cyber companion。`,
        origin_story: `由用户主动建立关系；希望被称为「${userName.trim() || "你"}」。`,
      },
      persona: {
        persona_summary: communicationStyle.trim(),
        communication_style_summary: communicationStyle.trim(),
        presence_style: presenceStyle,
      },
      contract: {
        relationship_role: relationshipRole,
        contract_summary: context.trim() || `从彼此尊重、逐步了解开始建立长期${relationshipRole === "companion" ? "伙伴" : "协作"}关系。`,
        contract_json: { user_preferred_name: userName.trim() || null, companionship_context: context.trim() || null },
      },
      boundary: {
        boundary_json: { quiet_hours: { enabled: true, start: quietStart, end: quietEnd }, focus_mode: "respect" },
        presence_interrupt_policy: presenceStyle === "quiet" ? "user_initiated_only" : "respect_existing_boundary",
      },
      });
      setName("");
      setUserName("");
      setContext("");
      setRelationshipRole("companion");
    } catch {
      // The calling surface keeps the actionable API error visible.
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <section className="dynamic-glass companion-panel companion-create-panel">
      <div className="companion-panel-header">
        <div className="companion-panel-icon"><Plus size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>认识一位新伙伴</h2>
          <p>先确认关系起点与边界。人格会在长期相处中成长，不需要一次填写完整“角色卡”。</p>
        </div>
        {onCancel ? <button type="button" className="companion-create-close" onClick={onCancel} aria-label="取消创建" disabled={creating || submitting}><X size={18} /></button> : null}
      </div>
      <form className="companion-form-grid" onSubmit={submit}>
        <Field label="伙伴希望叫什么名字" value={name} onChange={setName} required />
        <Field label="希望伙伴如何称呼你" value={userName} onChange={setUserName} />
        <label className="companion-form-field">
          <span>你们想从怎样的关系开始</span>
          <select value={relationshipRole} onChange={(event) => setRelationshipRole(event.target.value)}>
            <option value="companion">长期伙伴</option>
            <option value="collaborator">协作搭档</option>
            <option value="mentor">学习伙伴</option>
            <option value="observer">安静观察者</option>
          </select>
        </label>
        <Field label="最希望一起经历什么" value={context} onChange={setContext} multiline />
        <Field label="希望怎样交流" value={communicationStyle} onChange={setCommunicationStyle} multiline />
        <label className="companion-form-field"><span>主动陪伴程度</span><select value={presenceStyle} onChange={(event) => setPresenceStyle(event.target.value)}><option value="quiet">克制地提醒</option><option value="balanced">自然接续</option><option value="expressive">更积极表达</option></select></label>
        <div className="companion-quiet-hours"><Field label="安静时段开始" type="time" value={quietStart} onChange={setQuietStart} /><Field label="安静时段结束" type="time" value={quietEnd} onChange={setQuietEnd} /></div>
        <p className="companion-create-safety"><ShieldCheck size={16} /> 私有记忆默认隔离；共享、跨伙伴与长期记忆仍需你的确认。</p>
        <div className="companion-form-actions">
          {message && <span className="companion-form-message">{message}</span>}
          <button type="submit" className="glass-btn glass-btn-primary" disabled={!canCreate}>
            {creating ? "正在建立关系…" : "开始第一次相识"}
          </button>
        </div>
      </form>
    </section>
  );
}

function Field({ label, value, onChange, required, multiline, type = "text" }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  multiline?: boolean;
  type?: string;
}) {
  return (
    <label className="companion-form-field">
      <span>{label}</span>
      {multiline ? (
        <textarea value={value} onChange={(event) => onChange(event.target.value)} required={required} rows={3} />
      ) : (
        <input type={type} value={value} onChange={(event) => onChange(event.target.value)} required={required} />
      )}
    </label>
  );
}
