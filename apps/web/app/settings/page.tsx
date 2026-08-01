"use client";

import Link from "next/link";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";
import { settingsRouteGroups } from "@/lib/navigation/settingsRoutes";

export default function SettingsOverviewPage() {
  const companionContext = useActiveCompanionContext();

  return (
    <div className="settings-overview">
      <header className="settings-overview-hero">
        <p>ECHORA SETTINGS</p>
        <h1>让陪伴保持清晰，也保留必要的边界</h1>
        <span>伙伴体验、自动化和高级证据集中在这里。选择左侧分类进入具体设置；每个页面只保留当前任务需要的操作。</span>
      </header>
      <section className="settings-overview-groups" aria-label="设置概览">
        {settingsRouteGroups.map((group) => (
          <article key={group.label}>
            <div><small>{group.advanced ? "高级" : "常用"}</small><h2>{group.label}</h2></div>
            <ul>{group.items.map((item) => {
              const href = item.href(companionContext.activeCompanionId);
              return <li key={item.key}><Link href={href}><item.icon size={17} aria-hidden="true" /><span><strong>{item.label}</strong><small>{item.description}</small></span></Link></li>;
            })}</ul>
          </article>
        ))}</section>
    </div>
  );
}
