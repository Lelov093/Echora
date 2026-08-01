"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, ShieldCheck, UsersRound } from "lucide-react";
import { listSharedScenes } from "@/lib/api/sharedScenes";
import { DataState } from "@/components/patterns/DataState";
import { DETAIL_PAGE_SIZE, Pagination, usePageParam } from "@/components/patterns/Pagination";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";

export function SharedScenes() {
  const companion = useActiveCompanionContext();
  const [page, setPage] = usePageParam();
  const scenes = useQuery({ queryKey: ["shared-scenes", "product", page], queryFn: () => listSharedScenes({ scope: "product", page, page_size: DETAIL_PAGE_SIZE }) });
  if (scenes.isLoading) return <DataState kind="loading" title="正在读取共享场景" />;
  if (scenes.isError || !scenes.data) return <DataState kind="error" title="暂时无法读取共享场景" />;
  const backHref = companion.activeCompanionId ? `/companions/${companion.activeCompanionId}` : "/companions";
  return <section className="shared-scenes-page"><header><Link href={backHref}><ArrowLeft size={17} />返回伙伴空间</Link><span>受治理的共同空间</span></header><div className="shared-scenes-hero"><div><span>共享场景</span><h1>被明确邀请的<br />共同片刻。</h1></div><p>只有明确加入的参与者才会出现在这里；共同记忆始终保留审核门槛。</p></div><div className="shared-scenes-list">{scenes.data.items.length ? <>{scenes.data.items.map((scene) => <Link href={`/scenes/${scene.id}`} key={scene.id} className="scene-row"><span className="scene-orb"><UsersRound size={18} /></span><div><small>{scene.scene_status === "active" ? "进行中" : "已归档"} · {scene.visibility_scope}</small><h2>{scene.scene_title || "未命名共享场景"}</h2><p>{scene.scene_summary || scene.focal_topic || "尚未留下可共享的摘要"}</p><span className="scene-review"><ShieldCheck size={14} /> {scene.shared_experiences.some((item) => item.review_required) ? "存在待审核的共同经历" : "共同记忆需要审核"}</span></div><ArrowRight className="scene-arrow" size={18} /></Link>)}<Pagination pagination={scenes.data.pagination} page={page} onPageChange={setPage} disabled={scenes.isFetching} /></> : <DataState kind="empty" title="还没有共享场景" description="当伙伴明确受邀、参与角色确认后，共享场景才会出现在这里。" />}</div></section>;
}
