"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Eye, LockKeyhole, Mic, ShieldCheck, UsersRound } from "lucide-react";
import { getSharedScene } from "@/lib/api/sharedScenes";
import { useCompanionWorkspaceQuery } from "@/lib/queries/companions";
import { DataState } from "@/components/patterns/DataState";

const roleLabel: Record<string, string> = { primary_companion: "主伙伴", active_companion: "参与伙伴", observer: "观察者", user: "你" };

export function SharedSceneDetail({ sceneId }: { sceneId: string }) {
  const scene = useQuery({ queryKey: ["shared-scenes", sceneId], queryFn: () => getSharedScene(sceneId) });
  const ownerWorkspace = useCompanionWorkspaceQuery(scene.data?.owner_companion_id || "");
  if (scene.isLoading) return <DataState kind="loading" title="正在打开共享场景" />;
  if (scene.isError || !scene.data) return <DataState kind="error" title="暂时无法打开这个共享场景" />;
  const data = scene.data;
  const governance = ownerWorkspace.data?.governance;
  return <section className="shared-scene-detail"><header><Link href="/scenes"><ArrowLeft size={17} />返回共享场景</Link><span>受治理的共同空间</span></header><div className="scene-detail-hero"><p>{data.scene_status === "active" ? "正在进行" : "已结束"}</p><h1>{data.scene_title || "未命名共享场景"}</h1><span>{data.scene_summary || data.focal_topic || "没有可公开的场景摘要"}</span></div><div className="scene-detail-grid"><main><section className="scene-detail-section"><h2><UsersRound size={18} />参与者与角色</h2>{data.participants.length ? <ul className="scene-participants">{data.participants.map((participant) => <li key={participant.id}><div><strong>{participant.name}</strong><span>{roleLabel[participant.participant_role] || participant.participant_role}</span></div><small>{participant.can_speak ? <><Mic size={13} />可发言</> : <><Eye size={13} />仅观察</>} · {participant.visibility_scope}</small></li>)}</ul> : <p className="scene-empty">此场景没有可展示的参与者记录。</p>}</section><section className="scene-detail-section"><h2><ShieldCheck size={18} />共同经历</h2>{data.shared_experiences.length ? <ul className="scene-experiences">{data.shared_experiences.map((item) => <li key={item.id}><strong>{item.experience_title || "共同经历候选"}</strong><p>{item.experience_summary}</p><span>{item.review_required ? "等待审核后才会成为共享记忆" : "已按策略记录"}</span></li>)}</ul> : <p className="scene-empty">还没有可记录的共同经历。</p>}</section></main><aside><LockKeyhole size={19} /><h2>边界仍在生效</h2><p>观察者不会被当作发言者；共享内容不会自动进入任何伙伴的私有记忆。</p><small>{governance ? `场景 owner：${governance.hard_stop_active ? `hard stop 已启用（${governance.hard_stop_scope}）` : "未启用 hard stop"}；已撤销频道 ${governance.revoked_channels} 个。该状态不代表其他参与者。` : "正在读取场景 owner 的治理状态；不会推断其他参与者的权限。"}</small></aside></div></section>;
}
