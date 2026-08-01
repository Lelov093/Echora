"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { MessagesSquare, Settings2, UserRound } from "lucide-react";
import { DataState } from "@/components/patterns/DataState";
import { useCompanionRosterQuery } from "@/lib/queries/companions";
import { MultiCompanionHome } from "./MultiCompanionHome";
import { SingleCompanionHome } from "./SingleCompanionHome";

type HomeMode = "single" | "multi";
const HOME_PAGE_SIZE = 8;

type CompanionHomeProps = {
  mode: HomeMode;
  selectedCompanionId?: string;
  activePage: number;
  archivedPage: number;
  roomPage: number;
  singleQuery: string;
  roomQuery: string;
};

export function CompanionHome({ mode, selectedCompanionId, activePage, archivedPage, roomPage, singleQuery, roomQuery }: CompanionHomeProps) {
  const router = useRouter();
  const activeRoster = useCompanionRosterQuery("product", { page: activePage, pageSize: HOME_PAGE_SIZE, search: singleQuery });
  const archivedRoster = useCompanionRosterQuery("archived", { page: archivedPage, pageSize: HOME_PAGE_SIZE, search: singleQuery });

  if (activeRoster.isError || archivedRoster.isError) {
    return <DataState kind="error" title="暂时无法打开伙伴之家" description="请确认 Agent API 正在运行后重试。" />;
  }
  if (activeRoster.isLoading || archivedRoster.isLoading || !activeRoster.data || !archivedRoster.data) {
    return <DataState kind="loading" title="正在抵达伙伴之家" description="正在确认伙伴与聊天室的真实状态。" />;
  }
  const activeCompanions = activeRoster.data.items;
  const archivedCompanions = archivedRoster.data.items;

  return (
    <main className="companion-home">
      <nav className="companion-home-top-nav" aria-label="首页导航">
        <Link className="companion-home-brand" href="/" aria-label="Echora 首页"><span className="echora-wordmark-mark" aria-hidden="true" /><span><strong>Echora</strong><small>与伙伴共同生活</small></span></Link>
        <div className="companion-home-mode" role="tablist" aria-label="伙伴相处模式">
          <button type="button" role="tab" aria-selected={mode === "single"} onClick={() => router.replace(selectedCompanionId ? `/?mode=single&companion_id=${encodeURIComponent(selectedCompanionId)}` : "/", { scroll: false })}>
            <UserRound size={18} aria-hidden="true" />
            <span><strong>Single Companion</strong><small>一对一相处</small></span>
          </button>
          <button type="button" role="tab" aria-selected={mode === "multi"} onClick={() => router.replace("/?mode=multi", { scroll: false })}>
            <MessagesSquare size={18} aria-hidden="true" />
            <span><strong>Multi Companion</strong><small>聊天室与共同空间</small></span>
          </button>
        </div>
        <Link className="companion-home-settings" href="/settings" aria-label="打开设置"><Settings2 size={18} /><span>设置</span></Link>
      </nav>
      <header className="companion-home-header">
        <div>
          <span>ECHORA HOME</span>
          <h1>和谁一起度过此刻？</h1>
          <p>选择一位伙伴继续相处，或把熟悉的伙伴们邀请到同一个聊天室。</p>
        </div>
      </header>
      <section role="tabpanel" aria-label={mode === "single" ? "单伙伴" : "多伙伴"}>
        {mode === "single" ? (
          <SingleCompanionHome
            key={selectedCompanionId ?? "default"}
            activeCompanions={activeCompanions}
            archivedCompanions={archivedCompanions}
            activePagination={activeRoster.data.pagination}
            archivedPagination={archivedRoster.data.pagination}
            selectedCompanionId={selectedCompanionId}
            singleQuery={singleQuery}
          />
        ) : (
          <MultiCompanionHome activeCompanions={activeCompanions} activeTotal={activeRoster.data.pagination.total} roomPage={roomPage} roomQuery={roomQuery} />
        )}
      </section>
    </main>
  );
}
