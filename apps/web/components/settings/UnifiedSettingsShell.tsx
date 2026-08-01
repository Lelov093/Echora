"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ChevronDown, Home, MessageCircle, Settings2, ShieldCheck, UsersRound } from "lucide-react";
import { listConversations } from "@/lib/api/conversations";
import { useCompanionRosterQuery } from "@/lib/queries/companions";
import { useUIStore } from "@/lib/stores/appStore";
import { settingsItemIsActive, settingsRouteGroups, type SettingsRouteItem } from "@/lib/navigation/settingsRoutes";

export function UnifiedSettingsShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const roster = useCompanionRosterQuery("product");
  const activeCompanionId = useUIStore((state) => state.activeCompanionId);
  const setActiveCompanionId = useUIStore((state) => state.setActiveCompanionId);
  const companions = (roster.data?.items ?? []).map(({ id, name }) => ({ id, name }));
  const scopedCompanionId = pathname.match(/^\/settings\/companions\/([^/]+)/)?.[1];
  const companionId = scopedCompanionId ?? companions.find((companion) => companion.id === activeCompanionId)?.id ?? companions[0]?.id;
  const scopedCompanions = companionId && !companions.some((companion) => companion.id === companionId)
    ? [{ id: companionId, name: "当前伙伴（已归档或未载入）" }, ...companions]
    : companions;
  const returnTo = safeSettingsReturnTo(searchParams.get("return_to"));
  const currentRoomId = returnTo?.match(/^\/rooms\/([0-9a-f-]{36})$/i)?.[1];
  const recentConversation = useQuery({
    queryKey: ["settings-recent-conversation", companionId],
    queryFn: () => listConversations({ companion_id: companionId, status: "active", page: 1, page_size: 1 }),
    enabled: Boolean(companionId),
    staleTime: 30_000,
  });
  const conversationHref = companionId && recentConversation.data?.items[0]
    ? `/companions/${companionId}/conversations/${recentConversation.data.items[0].id}`
    : companionId ? `/?mode=single&companion_id=${encodeURIComponent(companionId)}` : "/?mode=single";

  useEffect(() => {
    if (companionId && activeCompanionId !== companionId) setActiveCompanionId(companionId);
  }, [activeCompanionId, companionId, setActiveCompanionId]);

  return (
    <section className="unified-settings-shell">
      <aside className="unified-settings-index" aria-label="设置分类">
        <nav className="unified-settings-exits" aria-label="离开设置">
          {returnTo ? <Link href={returnTo} className="is-return"><ArrowLeft size={16} aria-hidden="true" /><span>{currentRoomId ? "返回当前聊天室" : "返回原对话"}</span></Link> : null}
          <Link href="/"><Home size={16} aria-hidden="true" /><span>产品首页</span></Link>
          <Link href={conversationHref}><MessageCircle size={16} aria-hidden="true" /><span>{recentConversation.data?.items[0] ? "进入当前伙伴会话" : "开始伙伴会话"}</span></Link>
          <Link href={currentRoomId ? `/rooms/${currentRoomId}` : "/?mode=multi"}><UsersRound size={16} aria-hidden="true" /><span>{currentRoomId ? "打开当前聊天室" : "进入聊天室"}</span></Link>
        </nav>
        <header><Settings2 size={18} aria-hidden="true" /><div><small>ECHORA SETTINGS</small><h1>设置</h1></div></header>
        <p>日常能力优先；质量证据和系统状态保持可发现但默认折叠。</p>
        <label className="unified-settings-scope"><span>当前伙伴</span><select value={companionId ?? ""} disabled={scopedCompanions.length === 0} onChange={(event) => {
          const nextId = event.target.value;
          setActiveCompanionId(nextId);
          const scopedSurface = pathname.match(/^\/settings\/companions\/[^/]+\/(profile|memory|growth|affect|chronicle|presence)/)?.[1];
          if (scopedSurface) router.replace(withSettingsReturnTo(`/settings/companions/${nextId}/${scopedSurface}`, returnTo));
        }}>{scopedCompanions.length === 0 ? <option value="">尚无伙伴</option> : scopedCompanions.map((companion) => <option key={companion.id} value={companion.id}>{companion.name}</option>)}</select></label>
        <nav>
          {settingsRouteGroups.map((group) => {
            const active = group.items.some((item) => settingsItemIsActive(pathname, item.href(companionId)));
            return group.advanced ? (
              <details key={group.label} open={active}>
                <summary><span>{group.label}</span><ChevronDown size={15} /></summary>
                <SettingsLinks items={group.items} pathname={pathname} companionId={companionId} returnTo={returnTo} />
              </details>
            ) : <section key={group.label}><small>{group.label}</small><SettingsLinks items={group.items} pathname={pathname} companionId={companionId} returnTo={returnTo} /></section>;
          })}
        </nav>
        <footer><ShieldCheck size={15} />治理模式按伙伴独立生效；未接入的自动化会明确保持人工确认。</footer>
      </aside>
      <div className="unified-settings-detail" data-settings-visual-contract="presence-v1">{children}</div>
    </section>
  );
}

function SettingsLinks({ items, pathname, companionId, returnTo }: { items: SettingsRouteItem[]; pathname: string; companionId?: string; returnTo: string | null }) {
  return <div>{items.map(({ key, href: resolveHref, label, description, icon: Icon }) => {
    const href = resolveHref(companionId);
    return <Link key={key} href={withSettingsReturnTo(href, returnTo)} aria-current={settingsItemIsActive(pathname, href) ? "page" : undefined}><Icon size={17} aria-hidden="true" /><span><strong>{label}</strong><small>{description}</small></span></Link>;
  })}</div>;
}

export function safeSettingsReturnTo(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return null;
  let parsed: URL;
  try { parsed = new URL(value, "https://echora.local"); } catch { return null; }
  if (parsed.origin !== "https://echora.local" || parsed.search || parsed.hash) return null;
  if (/^\/companions\/[0-9a-f-]{36}\/conversations\/[0-9a-f-]{36}$/i.test(parsed.pathname)) return parsed.pathname;
  if (/^\/rooms\/[0-9a-f-]{36}$/i.test(parsed.pathname)) return parsed.pathname;
  return null;
}

function withSettingsReturnTo(href: string, returnTo: string | null): string {
  if (!returnTo) return href;
  const separator = href.includes("?") ? "&" : "?";
  return `${href}${separator}return_to=${encodeURIComponent(returnTo)}`;
}
