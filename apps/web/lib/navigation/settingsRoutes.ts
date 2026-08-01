import { Activity, Bot, BookHeart, Brain, CircleUserRound, Database, Radio, Settings2, ShieldCheck, Sparkles, UsersRound, Waves, Wrench } from "lucide-react";

export type SettingsRouteItem = {
  key: string;
  label: string;
  description: string;
  icon: typeof Settings2;
  href: (companionId?: string) => string;
};

export type SettingsRouteGroup = {
  label: string;
  advanced?: boolean;
  items: SettingsRouteItem[];
};

const companionRoute = (companionId: string | undefined, surface: string) =>
  companionId ? `/settings/companions/${companionId}/${surface}` : "/settings";

export const settingsRouteGroups: SettingsRouteGroup[] = [
  { label: "伙伴", items: [
    { key: "profile", label: "伙伴档案", description: "身份、关系与相处方式", icon: CircleUserRound, href: (id) => companionRoute(id, "profile") },
    { key: "memory", label: "记忆", description: "查看、修正与生命周期", icon: Brain, href: (id) => companionRoute(id, "memory") },
    { key: "growth", label: "成长", description: "候选、影响与确认", icon: Sparkles, href: (id) => companionRoute(id, "growth") },
    { key: "affect", label: "表达状态", description: "表达余韵、偏好与纠错", icon: Waves, href: (id) => companionRoute(id, "affect") },
    { key: "chronicle", label: "共同历程", description: "你们共同经历的片段", icon: BookHeart, href: (id) => companionRoute(id, "chronicle") },
  ] },
  { label: "交互与能力", items: [
    { key: "presence", label: "Presence", description: "安静时段与主动联系", icon: Radio, href: (id) => companionRoute(id, "presence") },
    { key: "rooms", label: "聊天室", description: "共同空间、成员与频道映射", icon: UsersRound, href: () => "/settings/rooms" },
    { key: "tools", label: "Tools", description: "对话工具与使用权限", icon: Wrench, href: () => "/settings/tools" },
    { key: "discord", label: "Discord", description: "Bot、伙伴与对话连续性", icon: Bot, href: () => "/settings/channels/discord" },
  ] },
  { label: "控制与隐私", items: [
    { key: "automation", label: "自动化参与", description: "参与程度、分析建议与智能策略", icon: ShieldCheck, href: () => "/settings/automation" },
    { key: "review", label: "待确认", description: "仍需你决定的记忆与变化", icon: ShieldCheck, href: () => "/settings/review" },
    { key: "data-privacy", label: "数据与隐私", description: "保留、导出、遗忘与删除预检", icon: Database, href: () => "/settings/system/data-privacy" },
  ] },
  { label: "质量与高级", advanced: true, items: [
    { key: "quality", label: "质量概览", description: "需要处理的问题与建议", icon: Activity, href: () => "/settings/quality" },
  ] },
  { label: "系统", advanced: true, items: [
    { key: "providers", label: "模型与连接", description: "LLM、Embedding 与 Discord 凭据", icon: Bot, href: () => "/settings/system/providers" },
    { key: "diagnostics", label: "系统状态", description: "连接健康与问题定位", icon: Activity, href: () => "/settings/system/diagnostics" },
  ] },
];

export function settingsItemIsActive(pathname: string, href: string) {
  if (href === "/settings") return pathname === href;
  if (href === "/settings/quality") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}
