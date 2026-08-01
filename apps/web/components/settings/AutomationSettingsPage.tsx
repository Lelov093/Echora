"use client";

import Link from "next/link";
import { Brain, KeyRound, Radio, ShieldCheck, Waves } from "lucide-react";
import { GovernanceAutomationPanel } from "@/components/settings/GovernanceAutomationPanel";
import { MemorySelectionPolicyPanel } from "@/components/settings/MemorySelectionPolicyPanel";
import { PresenceTimingPolicyPanel } from "@/components/settings/PresenceTimingPolicyPanel";
import { SettingsViewHeader } from "@/components/settings/SettingsView";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";

export function AutomationSettingsPage() {
  const companion = useActiveCompanionContext();
  const companionId = companion.activeCompanionId;
  const scoped = (surface: string) => companionId ? `/settings/companions/${companionId}/${surface}` : "/settings";
  const owners = [
    { icon: Radio, title: "主动联系与安静时段", detail: "Presence 是节奏、打断、通知与 meaningful silence 的唯一配置入口。", href: scoped("presence"), action: "前往 Presence" },
    { icon: Brain, title: "记忆与敏感内容", detail: "Memory 管理保存策略、敏感内容、纠错与忘记；候选仍由待确认处理。", href: scoped("memory"), action: "前往 Memory" },
    { icon: Waves, title: "表达状态", detail: "Affect 独立管理表达偏好与纠错，治理模式只决定支持范围内的自动参与。", href: scoped("affect"), action: "前往 Affect" },
    { icon: KeyRound, title: "工具权限与不可绕过边界", detail: "工具使用权限在 Tools 中设置；hard stop、revoke 与渠道约束始终高于自动化模式。", href: "/settings/tools", action: "前往 Tools" },
  ];

  return <div className="automation-settings-flow">
    <SettingsViewHeader eyebrow="设置 / 自动化与权限" title="自动化参与" description="决定 Echora 在各领域可以自动参与到什么程度；具体领域配置仍由各自主视图负责。" icon={ShieldCheck} aside={<><strong>边界优先于自动化</strong><p>不可绕过边界 ＞ 领域配置 ＞ effective mode ＞ 当前运行状态。</p></>} />
    <GovernanceAutomationPanel companionId={companionId} />
    <MemorySelectionPolicyPanel companionId={companionId} />
    <PresenceTimingPolicyPanel companionId={companionId} />
    <section className="settings-owner-directory" aria-labelledby="settings-owner-title">
      <header><small>CANONICAL SETTINGS</small><h2 id="settings-owner-title">具体配置，各归其位</h2><p>这里不复制领域表单。每张摘要都通向唯一写入口，避免同一状态在多个页面分别保存。</p></header>
      <div>{owners.map((owner) => <article key={owner.title}><owner.icon size={18} aria-hidden="true" /><div><h3>{owner.title}</h3><p>{owner.detail}</p></div><Link href={owner.href}>{owner.action}</Link></article>)}</div>
    </section>
  </div>;
}
