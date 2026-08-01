export type SettingsMutationOwner = {
  key: string;
  label: string;
  owner: string;
  href: string;
  scope: string;
  legacyRoutes?: string[];
  mode: "write" | "read-only" | "domain-review";
};

export const settingsMutationOwners: SettingsMutationOwner[] = [
  { key: "identity", label: "伙伴身份、人格与关系约定", owner: "伙伴档案", href: "/settings/companions/{companion_id}/profile", scope: "当前 Companion", mode: "write" },
  { key: "visibility", label: "伙伴可见性与跨范围读取", owner: "伙伴档案", href: "/settings/companions/{companion_id}/profile", scope: "当前 Companion", mode: "write" },
  { key: "memory", label: "记忆保存、敏感策略与生命周期", owner: "记忆", href: "/settings/companions/{companion_id}/memory", scope: "当前 Companion 的私有记忆", mode: "write" },
  { key: "presence", label: "主动联系、时间、频率与安静边界", owner: "Presence", href: "/settings/companions/{companion_id}/presence", scope: "当前 Companion", mode: "write" },
  { key: "affect", label: "表达状态、强度与纠错", owner: "表达状态", href: "/settings/companions/{companion_id}/affect", scope: "当前 Companion", mode: "write" },
  { key: "projects", label: "项目与任务生命周期", owner: "内部 Project 契约", href: "/settings", scope: "用户项目（普通产品面已退役）", legacyRoutes: ["/projects", "/settings/projects", "/settings/integrations", "/studio/integrations"], mode: "read-only" },
  { key: "tools", label: "工具运行、确认与权限", owner: "Tools", href: "/settings/tools", scope: "工具定义、运行与 Companion 权限", legacyRoutes: ["/settings/permissions", "/settings/integrations", "/studio/integrations"], mode: "write" },
  { key: "channels", label: "渠道绑定、连续性与撤销", owner: "Discord", href: "/settings/channels/discord", scope: "Discord Bot / Companion / Conversation binding", legacyRoutes: ["/settings/channels", "/settings/channels/revoke", "/settings/integrations", "/studio/integrations"], mode: "write" },
  { key: "discord", label: "Discord Bot identity 与 DM continuity", owner: "Discord", href: "/settings/channels/discord", scope: "Discord identity / Companion binding", legacyRoutes: ["/settings/integrations", "/studio/integrations"], mode: "write" },
  { key: "rooms", label: "Room roster 与 Discord Channel mapping", owner: "具体 Room 设置", href: "/settings/rooms", scope: "一个 Web Room", legacyRoutes: ["/settings/integrations", "/studio/integrations"], mode: "write" },
  { key: "automation", label: "Governance mode、domain override 与 rollback", owner: "自动化与边界", href: "/settings/automation", scope: "当前 Companion", mode: "write" },
  { key: "data-privacy", label: "数据保留、导出与删除预检", owner: "数据与隐私", href: "/settings/system/data-privacy", scope: "当前 Companion", mode: "write" },
  { key: "review", label: "Memory、Growth、Relationship 与跨边界决定", owner: "待确认", href: "/settings/review", scope: "原始领域对象与终态", mode: "domain-review" },
  { key: "quality", label: "Evaluation、Bad Case、Regression 与 Replay", owner: "质量", href: "/settings/quality", scope: "质量证据", mode: "write" },
  { key: "providers", label: "LLM、Embedding 与 Discord 连接配置", owner: "安全配置中心", href: "/settings/system/providers", scope: "本机系统运行配置；Secret 仅可替换", legacyRoutes: ["/settings/integrations", "/studio/integrations", "/llm-provider-configs", "/llm-model-configs"], mode: "write" },
];
