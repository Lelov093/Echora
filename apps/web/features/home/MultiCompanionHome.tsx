"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArrowUpRight, Eye, MessageSquarePlus, PencilLine, Plus, Search, ShieldCheck, UsersRound, X } from "lucide-react";
import { CompanionOrb } from "@/components/companion/CompanionOrb";
import {
  archiveCompanionRoom,
  createCompanionRoom,
  getCoPresenceSession,
  listCoPresenceSessions,
  updateCompanionRoom,
  type CompanionRoomCreateInput,
} from "@/lib/api/coPresence";
import { listSharedScenes } from "@/lib/api/sharedScenes";
import { getCompanion } from "@/lib/api/companions";
import { useCompanionRosterQuery } from "@/lib/queries/companions";
import type { CoPresenceSessionBundle, CompanionBundle, SharedSceneBundle } from "@/lib/types";
import { HomePagination } from "./HomePagination";

type MultiCompanionHomeProps = {
  activeCompanions: CompanionBundle[];
  activeTotal: number;
  roomPage: number;
  roomQuery: string;
};
const HOME_PAGE_SIZE = 8;

export function MultiCompanionHome({ activeCompanions, activeTotal, roomPage, roomQuery }: MultiCompanionHomeProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const client = useQueryClient();
  const ownerId = activeCompanions[0]?.user_id || "";
  const [selectedId, setSelectedId] = useState("");
  const [creating, setCreating] = useState(() => searchParams.get("create_room") === "1");
  const sessions = useQuery({
    queryKey: ["companion-rooms", ownerId, "product", roomPage, HOME_PAGE_SIZE, roomQuery],
    queryFn: () => listCoPresenceSessions({ user_id: ownerId, scope: "product", session_source: "companion_home", search: roomQuery || undefined, page: roomPage, page_size: HOME_PAGE_SIZE }),
    enabled: Boolean(ownerId),
  });
  const rooms = sessions.data?.items ?? [];
  const firstRoomId = sessions.data?.items[0]?.id;
  const effectiveSelectedId = selectedId || firstRoomId || "";
  const selectedOnPage = rooms.find((room) => room.id === effectiveSelectedId) ?? null;
  const selectedRoom = useQuery({
    queryKey: ["companion-rooms", "selection", effectiveSelectedId],
    queryFn: () => getCoPresenceSession(effectiveSelectedId),
    enabled: Boolean(effectiveSelectedId && !selectedOnPage),
  });
  const selected = selectedOnPage ?? selectedRoom.data ?? rooms[0] ?? null;
  const scene = useQuery({
    queryKey: ["companion-rooms", selected?.id, "scene"],
    queryFn: () => listSharedScenes({ user_id: ownerId, scope: "all", co_presence_session_id: selected?.id, page: 1, page_size: 1 }),
    enabled: Boolean(ownerId && selected?.id),
  });
  const selectedScene = scene.data?.items[0] ?? null;
  const replaceSearch = (updates: Record<string, string | number | null>) => {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, String(value));
    }
    router.replace(`/?${next.toString()}`, { scroll: false });
  };
  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    const nextQuery = String(new FormData(event.currentTarget as HTMLFormElement).get("room_q") ?? "").trim();
    setSelectedId((current) => current || firstRoomId || "");
    replaceSearch({ room_q: nextQuery || null, room_page: 1 });
  };
  const create = useMutation({
    mutationFn: createCompanionRoom,
    onSuccess: async (result) => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["companion-rooms", ownerId] }),
        client.invalidateQueries({ queryKey: ["companion-rooms"] }),
      ]);
      setSelectedId(result.session.id);
      setCreating(false);
      replaceSearch({ create_room: null });
    },
  });

  if (activeTotal === 0) {
    return <MultiLockedEmpty />;
  }

  return (
    <div className="companion-home-workspace multi-home-workspace">
      <aside className="companion-home-index" aria-label="聊天室列表">
        <div className="companion-home-index-heading">
          <div><small>我的聊天室</small><strong>{sessions.data?.pagination.total ?? 0} 个共同空间</strong></div>
          <button type="button" onClick={() => setCreating(true)} aria-label="创建聊天室"><Plus size={19} /></button>
        </div>
        <form className="companion-home-search" role="search" onSubmit={submitSearch}><Search size={17} aria-hidden="true" /><label className="sr-only" htmlFor="home-room-search">搜索聊天室</label><input key={roomQuery} id="home-room-search" name="room_q" defaultValue={roomQuery} placeholder="搜索聊天室" /><button type="submit">搜索</button></form>
        <div className="companion-home-list room-home-list">
          <section>
            <small>共同空间</small>
            {rooms.map((room) => (
                <button key={room.id} type="button" className={selected?.id === room.id ? "is-selected" : ""} onClick={() => setSelectedId(room.id)}>
                <span className="room-list-icon"><UsersRound size={18} /></span>
                <span><strong>{room.session_title}</strong><small>{room.participants.filter((item) => item.participant_type === "companion").length} 位伙伴</small></span>
                <em>{room.session_status === "active" ? "进行中" : "已结束"}</em>
              </button>
            ))}
          </section>
          <HomePagination label="伙伴聊天室" page={sessions.data?.pagination.page ?? roomPage} totalPages={sessions.data?.pagination.total_pages ?? 1} total={sessions.data?.pagination.total ?? 0} onPageChange={(page) => { setSelectedId((current) => current || firstRoomId || ""); replaceSearch({ room_page: page }); }} />
          {rooms.length === 0 ? <p className="companion-home-list-empty">{roomQuery ? "没有找到匹配的聊天室。" : "还没有聊天室。"}</p> : null}
        </div>
        <footer><ShieldCheck size={15} /> 跨伙伴记忆默认待确认；观察者不会自动获得发言权。</footer>
      </aside>
      <section className="companion-home-detail">
        {sessions.isLoading || selectedRoom.isLoading || scene.isLoading ? <p className="home-inline-state">正在读取聊天室…</p> : sessions.isError || selectedRoom.isError || scene.isError ? <p className="home-inline-state is-error">聊天室暂时不可用，请确认后端状态。</p> : selected ? (
          <CompanionRoomDetail
            key={selected.id}
            room={selected}
            scene={selectedScene}
          />
        ) : (
          <EmptyRoomHome companionCount={activeCompanions.length} onCreate={() => setCreating(true)} />
        )}
      </section>
      {creating ? (
        <div className="companion-create-backdrop" role="presentation">
          <div className="companion-create-dialog room-create-dialog" role="dialog" aria-modal="true" aria-label="创建聊天室">
            <CompanionRoomCreatePanel
              pending={create.isPending}
              error={create.error instanceof Error ? create.error.message : null}
              onCancel={() => { setCreating(false); create.reset(); replaceSearch({ create_room: null }); }}
              onCreate={(payload) => create.mutate(payload)}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CompanionRoomDetail({ room, scene }: {
  room: CoPresenceSessionBundle;
  scene: SharedSceneBundle | null;
}) {
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(room.session_title);
  const [summary, setSummary] = useState(room.session_summary || "");
  const [confirmingArchive, setConfirmingArchive] = useState(false);
  const [archiveWarning, setArchiveWarning] = useState("");
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["companion-rooms"] }),
  ]);
  const save = useMutation({ mutationFn: () => updateCompanionRoom(room.id, { title, summary }), onSuccess: async () => { await refresh(); setEditing(false); } });
  const archive = useMutation({
    mutationFn: () => archiveCompanionRoom(room.id),
    onSuccess: async (result) => {
      await refresh();
      setConfirmingArchive(false);
      setArchiveWarning(
        result.scene_close_failures.length > 0
          ? `聊天室已结束，但有 ${result.scene_close_failures.length} 个共享场景未能同步关闭，请稍后在设置中复核。`
          : "",
      );
    },
  });
  const companionParticipants = room.participants.filter((item) => item.participant_type === "companion");
  const participantIds = Array.from(new Set([room.primary_companion_id, ...companionParticipants.map((item) => item.participant_companion_id).filter((id): id is string => Boolean(id))]));
  const companionQueries = useQueries({ queries: participantIds.map((companionId) => ({
    queryKey: ["companions", companionId, "room-member"],
    queryFn: () => getCompanion(companionId),
    staleTime: 30_000,
  })) });
  const companionMap = new Map(companionQueries.flatMap((query) => query.data ? [[query.data.id, query.data] as const] : []));
  const primary = companionMap.get(room.primary_companion_id);

  return (
    <div className="companion-room-home-detail">
      <header className="room-home-hero">
        <div className="room-home-orbs">
          {companionParticipants.slice(0, 4).map((participant, index) => <CompanionOrb key={participant.id} name={companionMap.get(participant.participant_companion_id || "")?.name || "伙伴"} index={index} size="medium" />)}
        </div>
        <div><small>{room.session_status === "active" ? "ACTIVE COMPANION ROOM" : "ARCHIVED COMPANION ROOM"}</small><h2>{room.session_title}</h2><p>{room.session_summary || "一个让伙伴们在明确边界内共同相处的空间。"}</p></div>
        <span className={scene ? "room-scene-ready" : "room-scene-unavailable"}>{scene ? "聊天室基础已建立" : "聊天室基础尚未建立"}</span>
        <Link className="home-primary-action" href={`/rooms/${room.id}`}>进入聊天室<ArrowUpRight size={17} /></Link>
      </header>

      <div className="room-home-body">
        <section className="room-home-info">
          <header><div><small>聊天室信息</small><h3>共同空间的名称与主题</h3></div>{!editing && room.session_status === "active" ? <button type="button" onClick={() => setEditing(true)}><PencilLine size={16} />编辑</button> : null}</header>
          {editing ? <div className="room-home-form"><label><span>聊天室名称</span><input maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)} /></label><label><span>此刻想一起聊什么</span><textarea rows={4} maxLength={1000} value={summary} onChange={(event) => setSummary(event.target.value)} /></label><div className="home-form-actions"><button type="button" className="home-primary-action" disabled={!title.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "正在保存…" : "保存聊天室"}</button><button type="button" onClick={() => setEditing(false)} disabled={save.isPending}>取消</button>{save.isError ? <span role="alert">保存失败，原信息已保留。</span> : null}</div></div> : <div className="room-home-topic"><small>当前主题</small><p>{room.session_summary || "暂时没有明确主题，先从自然聊天开始。"}</p></div>}
        </section>
        <aside className="room-home-members">
          <small>群成员</small><h3>{companionParticipants.length} 位伙伴与你</h3>
          <div>
            <article><span className="room-member-user">你</span><p><strong>你</strong><small>群主 · 最高权限</small></p></article>
            {companionParticipants.map((participant, index) => {
              const companion = companionMap.get(participant.participant_companion_id || "");
              const observing = participant.participant_role.includes("observ") || !participant.can_speak;
              return <article key={participant.id}><CompanionOrb name={companion?.name || "伙伴"} index={index} size="small" /><p><strong>{companion?.name || "未知伙伴"}{participant.participant_companion_id === primary?.id ? " · 主伙伴" : ""}</strong><small>{observing ? "观察模式 · 不会自动发言" : "允许发言 · 共享记忆仍待确认"}</small></p>{observing ? <Eye size={16} aria-label="观察模式" /> : null}</article>;
            })}
          </div>
          <p className="room-home-boundary"><ShieldCheck size={15} /> 私有记忆不因加入房间而自动共享。</p>
        </aside>
      </div>
      {archiveWarning ? <p className="home-inline-state is-error" role="status">{archiveWarning}</p> : null}
      {room.session_status === "active" ? <section className="room-home-lifecycle"><div><small>房间生命周期</small><h3>结束并归档聊天室</h3><p>结束后所有参与者退出，相关共享场景关闭；历史与审核证据继续保留。</p></div>{confirmingArchive ? <div className="home-confirm-block"><p>确认结束这个聊天室？该操作不会删除历史。</p><div><button type="button" disabled={archive.isPending} onClick={() => archive.mutate()}>{archive.isPending ? "正在结束…" : "确认结束"}</button><button type="button" onClick={() => setConfirmingArchive(false)}>取消</button></div>{archive.isError ? <span role="alert">聊天室未能安全结束，请重试。</span> : null}</div> : <button type="button" className="home-lifecycle-action" onClick={() => setConfirmingArchive(true)}><Archive size={16} />结束聊天室</button>}</section> : null}
    </div>
  );
}

function CompanionRoomCreatePanel({ pending, error, onCancel, onCreate }: {
  pending: boolean;
  error: string | null;
  onCancel: () => void;
  onCreate: (payload: CompanionRoomCreateInput) => void;
}) {
  const [page, setPage] = useState(1);
  const companionsQuery = useCompanionRosterQuery("product", { page, pageSize: HOME_PAGE_SIZE });
  const companions = companionsQuery.data?.items ?? [];
  const [title, setTitle] = useState("一起聊聊");
  const [summary, setSummary] = useState("");
  const [primaryId, setPrimaryId] = useState("");
  const [primaryCompanion, setPrimaryCompanion] = useState<CompanionBundle | null>(null);
  const [selected, setSelected] = useState<Record<string, "active_companion" | "observing_companion">>({});
  const effectivePrimaryId = primaryId || companions[0]?.id || "";
  const toggle = (id: string) => setSelected((current) => current[id] ? Object.fromEntries(Object.entries(current).filter(([key]) => key !== id)) : { ...current, [id]: "active_companion" });
  const primaryOptions = primaryCompanion && !companions.some((item) => item.id === primaryCompanion.id)
    ? [primaryCompanion, ...companions]
    : companions;
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !effectivePrimaryId || pending) return;
    onCreate({ primary_companion_id: effectivePrimaryId, title: title.trim(), summary: summary.trim() || undefined, participants: Object.entries(selected).filter(([id]) => id !== effectivePrimaryId).map(([companion_id, role]) => ({ companion_id, role })) });
  };
  return <section className="dynamic-glass companion-panel room-create-panel"><div className="companion-panel-header"><div className="companion-panel-icon"><MessageSquarePlus size={17} /></div><div><h2>创建一个伙伴聊天室</h2><p>选择主伙伴与群成员。观察模式不会被自动升级为发言。</p></div><button type="button" className="companion-create-close" onClick={onCancel} aria-label="取消创建"><X size={18} /></button></div>{companionsQuery.isLoading ? <p className="home-inline-state">正在读取伙伴…</p> : companionsQuery.isError ? <p className="home-inline-state is-error">伙伴列表暂时不可用。</p> : <form className="room-create-form" onSubmit={submit}><label><span>聊天室名称</span><input maxLength={120} required value={title} onChange={(event) => setTitle(event.target.value)} /></label><label><span>主伙伴</span><select value={effectivePrimaryId} onChange={(event) => { const nextPrimary = companions.find((item) => item.id === event.target.value) ?? primaryCompanion; setPrimaryId(event.target.value); setPrimaryCompanion(nextPrimary ?? null); setSelected((current) => Object.fromEntries(Object.entries(current).filter(([id]) => id !== event.target.value))); }}>{primaryOptions.map((companion) => <option key={companion.id} value={companion.id}>{companion.name}</option>)}</select></label><label className="is-wide"><span>想一起聊什么</span><textarea rows={3} maxLength={1000} value={summary} onChange={(event) => setSummary(event.target.value)} /></label><fieldset><legend>邀请其他伙伴</legend>{companions.filter((item) => item.id !== effectivePrimaryId).map((companion) => <div key={companion.id} className="room-invite-row"><label><input type="checkbox" checked={Boolean(selected[companion.id])} onChange={() => toggle(companion.id)} /><CompanionOrb name={companion.name} size="small" /><span>{companion.name}</span></label>{selected[companion.id] ? <select aria-label={`${companion.name} 的参与模式`} value={selected[companion.id]} onChange={(event) => setSelected({ ...selected, [companion.id]: event.target.value as "active_companion" | "observing_companion" })}><option value="active_companion">允许发言</option><option value="observing_companion">观察模式</option></select> : null}</div>)}</fieldset><HomePagination label="可邀请伙伴" page={companionsQuery.data?.pagination.page ?? page} totalPages={companionsQuery.data?.pagination.total_pages ?? 1} total={companionsQuery.data?.pagination.total ?? 0} onPageChange={(nextPage) => { const currentPrimary = companions.find((item) => item.id === effectivePrimaryId) ?? primaryCompanion; setPrimaryId(effectivePrimaryId); setPrimaryCompanion(currentPrimary ?? null); setPage(nextPage); }} /><p className="companion-create-safety"><ShieldCheck size={16} /> 已选择 {Object.keys(selected).length} 位；跨伙伴私有记忆默认禁止，共享候选仍需确认。</p><div className="companion-form-actions">{error ? <span className="companion-form-message" role="alert">{error}</span> : null}<button type="submit" className="glass-btn glass-btn-primary" disabled={!title.trim() || !effectivePrimaryId || pending}>{pending ? "正在建立聊天室…" : "创建聊天室"}</button></div></form>}</section>;
}

function EmptyRoomHome({ companionCount, onCreate }: { companionCount: number; onCreate: () => void }) {
  return <div className="companion-home-empty"><span className="room-empty-icon"><UsersRound size={34} /></span><small>MULTI-COMPANION</small><h2>{companionCount === 1 ? "先为你们建立一个基础房间" : "把熟悉的伙伴聚到一起"}</h2><p>{companionCount === 1 ? "当前只有一位伙伴，房间可以先建立；完整的多伙伴互动会在认识第二位伙伴后开放。" : "你是群主。伙伴可以发言或安静观察，所有跨伙伴共享仍遵循审核边界。"}</p><button type="button" className="home-primary-action" onClick={onCreate}><Plus size={18} />创建聊天室</button></div>;
}

function MultiLockedEmpty() {
  return <div className="companion-home-locked"><span><UsersRound size={30} /></span><small>MULTI-COMPANION</small><h2>先认识一位伙伴，再把朋友们聚到一起</h2><p>聊天室建立在真实的伙伴关系之上。请先切回“单伙伴”，创建至少一位伙伴。</p><div><ShieldCheck size={16} /> 不会用虚拟成员或默认 Bot 填充聊天室。</div></div>;
}
