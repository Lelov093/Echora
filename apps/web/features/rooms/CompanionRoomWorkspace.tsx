"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive, ArrowDown, Bot, ChevronLeft, CirclePause, Eye, Hash, Home, MessageSquarePlus,
  MoreHorizontal, Plus, RotateCcw, Send, Settings2, ShieldCheck, UserMinus,
  UserPlus, UsersRound, VolumeX, X,
} from "lucide-react";
import { CompanionOrb } from "@/components/companion/CompanionOrb";
import { DataState } from "@/components/patterns/DataState";
import { ConversationMessageContent } from "@/features/conversation/ConversationMessageContent";
import {
  archiveCompanionRoom,
  bindDiscordChannelToRoom,
  createDiscordRoomChannel,
  createDiscordRoomGuild,
  createCompanionRoomSuccessor,
  getCompanionRoom,
  inviteCompanionRoomMember,
  listCoPresenceSessions,
  listCompanionRoomMessages,
  listDiscordRoomBotIdentities,
  listDiscordRoomChannels,
  listDiscordRoomGuilds,
  listDiscordRoomIngresses,
  restoreCompanionRoom,
  retryCompanionRoomTurnStep,
  runCompanionRoomTurn,
  transitionCompanionRoomMember,
  transitionDiscordRoomBinding,
  updateCompanionRoom,
} from "@/lib/api/coPresence";
import { getCompanion } from "@/lib/api/companions";
import { useCompanionRosterQuery } from "@/lib/queries/companions";
import type { CompanionRoomBundle, CompanionRoomTurn, CoPresenceParticipant, DiscordRoomBotIdentity } from "@/lib/types";

type DrawerTab = "room" | "members" | "discord";

export function CompanionRoomWorkspace({ roomId }: { roomId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const client = useQueryClient();
  const [drawerOpen, setDrawerOpen] = useState(() => searchParams.get("settings") === "1");
  const [tab, setTab] = useState<DrawerTab>("room");
  const [draft, setDraft] = useState("");
  const [selectedTargets, setSelectedTargets] = useState<string[]>([]);
  const [lastTurn, setLastTurn] = useState<CompanionRoomTurn | null>(null);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const messagesViewportRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialScrollDoneRef = useRef(false);
  const stayAtBottomRef = useRef(true);
  const roomQuery = useQuery({ queryKey: ["companion-room", roomId], queryFn: () => getCompanionRoom(roomId) });
  const room = roomQuery.data;
  const roomsQuery = useQuery({
    queryKey: ["companion-rooms", "workspace"],
    queryFn: () => listCoPresenceSessions({ scope: "product", session_source: "companion_home", page: 1, page_size: 100 }),
  });
  const messagesQuery = useQuery({
    queryKey: ["companion-room", roomId, "messages", room?.conversation?.id],
    queryFn: () => listCompanionRoomMessages(roomId),
    enabled: Boolean(room?.conversation?.id),
    refetchInterval: room?.discord_channel?.binding_status === "active" ? 3_000 : false,
  });
  const messages = messagesQuery.data?.items ?? [];
  const companionIds = room ? Array.from(new Set(room.participants.flatMap(item => item.participant_companion_id ? [item.participant_companion_id] : []))) : [];
  const memberQueries = useQueries({ queries: companionIds.map(companionId => ({
    queryKey: ["companions", companionId, "room-workspace"],
    queryFn: () => getCompanion(companionId), staleTime: 30_000,
  })) });
  const companionMap = useMemo(
    () => new Map(memberQueries.flatMap(query => query.data ? [[query.data.id, query.data] as const] : [])),
    [memberQueries],
  );
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["companion-room", roomId] }),
      client.invalidateQueries({ queryKey: ["companion-rooms"] }),
    ]);
  };
  const refreshMessages = async () => {
    await client.invalidateQueries({ queryKey: ["companion-room", roomId, "messages"] });
  };
  const runTurn = useMutation({
    mutationFn: (content: string) => runCompanionRoomTurn(roomId, {
      content,
      target_companion_ids: selectedTargets,
      idempotency_key: crypto.randomUUID(),
    }),
    onSuccess: async turn => {
      setLastTurn(turn);
      setDraft("");
      await refreshMessages();
    },
  });
  const retryStep = useMutation({
    mutationFn: ({ turnId, stepId }: { turnId: string; stepId: string }) => retryCompanionRoomTurnStep(roomId, turnId, stepId),
    onSuccess: async turn => { setLastTurn(turn); await refreshMessages(); },
  });

  useEffect(() => {
    const viewport = messagesViewportRef.current;
    if (!viewport || !messagesQuery.data) return;
    const frame = window.requestAnimationFrame(() => {
      if (!initialScrollDoneRef.current || stayAtBottomRef.current) viewport.scrollTop = viewport.scrollHeight;
      initialScrollDoneRef.current = true;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messagesQuery.data, runTurn.isPending, retryStep.isPending]);

  useEffect(() => {
    const viewport = messagesViewportRef.current;
    if (!viewport || !messages.length) return;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActiveMessageId((visible.target as HTMLElement).dataset.messageId ?? null);
    }, { root: viewport, rootMargin: "-28% 0px -52% 0px", threshold: [0, 0.4, 0.8] });
    viewport.querySelectorAll<HTMLElement>("[data-message-id]").forEach(element => observer.observe(element));
    return () => observer.disconnect();
  }, [messages.length]);

  const handleMessagesScroll = () => {
    const viewport = messagesViewportRef.current;
    if (!viewport) return;
    const distance = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    stayAtBottomRef.current = distance < 120;
    setShowJumpToLatest(distance >= 160);
  };
  const jumpToLatest = () => {
    stayAtBottomRef.current = true;
    messagesEndRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  };

  if (roomQuery.isLoading) return <DataState kind="loading" title="正在进入聊天室" description="正在核对 Room、成员与渠道边界。" />;
  if (roomQuery.isError || !room) return <DataState kind="error" title="无法进入这个聊天室" description="聊天室不存在、当前用户无权访问，或服务端数据结构尚未就绪。" action={<Link className="echora-state-action" href="/?mode=multi">返回聊天室首页</Link>} />;

  const companionMembers = room.participants.filter(item => item.participant_type === "companion");
  const speakerMembers = companionMembers.filter(item => item.join_status === "active" && item.can_speak && !item.participant_role.includes("observ"));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.trim() || runTurn.isPending || !room.composer_enabled) return;
    stayAtBottomRef.current = true;
    runTurn.mutate(draft.trim());
  };
  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };
  const toggleTarget = (companionId: string) => setSelectedTargets(current =>
    current.includes(companionId) ? current.filter(id => id !== companionId) : current.length < 3 ? [...current, companionId] : current,
  );
  return (
    <main className="room-workspace">
      <aside className="room-workspace-sidebar" aria-label="聊天室导航">
        <header>
          <Link href="/?mode=multi" aria-label="返回伙伴首页"><span className="echora-wordmark-mark" /><strong>Echora</strong></Link>
          <button type="button" aria-label="新建聊天室" onClick={() => router.push("/?mode=multi&create_room=1")}><Plus size={18} /></button>
        </header>
        <div className="room-sidebar-label"><span>聊天室</span><small>{roomsQuery.data?.pagination.total ?? 0}</small></div>
        <nav className="room-sidebar-list" aria-label="切换聊天室">
          {(roomsQuery.data?.items ?? []).map(item => (
            <Link key={item.id} href={`/rooms/${item.id}`} aria-current={item.id === room.id ? "page" : undefined}>
              <span><UsersRound size={17} /></span>
              <span><strong>{item.session_title}</strong><small>{item.session_status === "active" ? "进行中" : "已归档"}</small></span>
            </Link>
          ))}
        </nav>
        <footer>
          <Link href="/?mode=multi"><Home size={17} /><span>聊天室首页</span></Link>
          <Link href={`/settings/rooms?return_to=${encodeURIComponent(`/rooms/${room.id}`)}`}><Settings2 size={17} /><span>聊天室通用设置</span></Link>
          <p><ShieldCheck size={14} />跨伙伴共享默认待确认</p>
        </footer>
      </aside>

      <section className="room-conversation-shell">
        <header className="room-conversation-header">
          <Link href="/?mode=multi" className="room-mobile-back" aria-label="返回聊天室列表"><ChevronLeft size={20} /></Link>
          <div className="room-header-orbs" aria-hidden="true">
            {companionMembers.slice(0, 3).map((member, index) => <CompanionOrb key={member.id} name={companionMap.get(member.participant_companion_id || "")?.name || "伙伴"} index={index} size="small" />)}
          </div>
          <div><h1>{room.session_title}</h1><p>{activeSummary(companionMembers)} · {room.discord_channel ? `#${room.discord_channel.channel_display_name}` : "仅 Web"}</p></div>
          <button type="button" className="room-more-button" aria-label="打开聊天室设置" aria-expanded={drawerOpen} onClick={() => setDrawerOpen(true)}><MoreHorizontal size={21} /></button>
        </header>

        <div className="room-message-scroll" ref={messagesViewportRef} onScroll={handleMessagesScroll} aria-live="polite">
          {messagesQuery.isLoading ? <p className="room-stream-state">正在读取共同历史…</p> : messages.length ? (
            <div className="room-message-list">
              {messages.map(message => <article id={`room-message-${message.id}`} data-message-id={message.id} key={message.id} className={`room-message is-${message.role}`}><div><strong>{message.role === "user" ? "你" : message.companion_name}</strong><time>{formatTime(message.created_at)}</time></div><ConversationMessageContent content={message.content} markdown={message.content_format === "markdown"} /></article>)}
              <div ref={messagesEndRef} aria-hidden="true" />
            </div>
          ) : (
            <div className="room-conversation-empty">
              <span><MessageSquarePlus size={30} /></span>
              <small>MULTI-COMPANION ROOM</small>
              <h2>共同空间已经准备好</h2>
              <p>{room.session_summary || "这里会保留你与伙伴们的共同对话。"}</p>
              <div>{companionMembers.map((member, index) => <span key={member.id}><CompanionOrb name={companionMap.get(member.participant_companion_id || "")?.name || "伙伴"} index={index} size="small" />{companionMap.get(member.participant_companion_id || "")?.name || "伙伴"}</span>)}</div>
            </div>
          )}
        </div>
        {messages.length > 5 ? <nav className="room-quick-index" aria-label="聊天室消息快速索引">{messages.map((message, index) => <button key={message.id} type="button" className={activeMessageId === message.id ? "is-active" : undefined} onClick={() => document.getElementById(`room-message-${message.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })} aria-label={`跳转到第 ${index + 1} 条${message.role === "user" ? "你的消息" : `${message.companion_name} 的回复`}`} title={`第 ${index + 1} 条消息`}><span /></button>)}</nav> : null}
        {showJumpToLatest ? <button type="button" className="room-jump-latest" onClick={jumpToLatest}><ArrowDown size={17} /><span>回到最新消息</span></button> : null}

        <div className="room-composer-wrap">
          <div className="room-target-strip" aria-label="选择本轮回复伙伴">
            <span>本轮发言</span>
            {speakerMembers.map(member => {
              const companionId = member.participant_companion_id || "";
              const selected = selectedTargets.includes(companionId);
              return <button key={member.id} type="button" aria-pressed={selected} onClick={() => toggleTarget(companionId)}>{companionMap.get(companionId)?.name || "伙伴"}</button>;
            })}
            <small>{selectedTargets.length ? `已指定 ${selectedTargets.length} 位` : "未指定时由当前发言列表共同回应（最多 3 位）"}</small>
          </div>
          {lastTurn && lastTurn.status !== "completed" ? <RoomTurnStatus turn={lastTurn} retrying={retryStep.isPending} onRetry={stepId => retryStep.mutate({ turnId: lastTurn.id, stepId })} /> : null}
          {runTurn.isError ? <p className="room-turn-error" role="alert">本轮没有完整执行。消息与失败证据已保留，请检查伙伴状态或 Provider 后重试。</p> : null}
          <form className="room-composer" onSubmit={submit}>
            <textarea value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={handleComposerKeyDown} disabled={!room.composer_enabled || runTurn.isPending} rows={1} placeholder="和伙伴们说点什么…也可以用 @伙伴名 点名" aria-label="聊天室消息输入" />
            <button type="submit" disabled={!draft.trim() || !room.composer_enabled || runTurn.isPending} aria-label="发送消息"><Send size={18} /></button>
            <small>{runTurn.isPending ? "伙伴们正在分别整理回应…" : "Enter 发送 · Shift + Enter 换行"}</small>
          </form>
        </div>
      </section>

      {drawerOpen ? <RoomSettingsDrawer room={room} companionMap={companionMap} tab={tab} setTab={setTab} onClose={() => setDrawerOpen(false)} onRefresh={refresh} /> : null}
    </main>
  );
}

function RoomTurnStatus({ turn, retrying, onRetry }: { turn: CompanionRoomTurn; retrying: boolean; onRetry: (stepId: string) => void }) {
  const suppressed = turn.steps.filter(step => step.status === "suppressed");
  const failed = turn.steps.filter(step => step.status === "failed");
  return <div className={`room-turn-status is-${turn.status}`} role="status">
    <strong>{turn.status === "partial_failed" ? "部分伙伴暂未回应" : turn.status === "suppressed" ? "本轮保持安静" : "本轮执行未完成"}</strong>
    {suppressed.length ? <span>{suppressed.map(step => `${step.companion_name}：${String(step.evidence.veto_reason || step.evidence.runtime_veto || "边界抑制")}`).join("；")}</span> : null}
    {failed.map(step => <span key={step.id}>{step.companion_name}：{String(step.error.message || "执行失败")}<button type="button" disabled={retrying} onClick={() => onRetry(step.id)}>重试这位伙伴</button></span>)}
  </div>;
}

function RoomSettingsDrawer({ room, companionMap, tab, setTab, onClose, onRefresh }: {
  room: CompanionRoomBundle;
  companionMap: Map<string, { id: string; name: string }>;
  tab: DrawerTab;
  setTab: (tab: DrawerTab) => void;
  onClose: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [title, setTitle] = useState(room.session_title);
  const [summary, setSummary] = useState(room.session_summary || "");
  const tabs: Array<[DrawerTab, string]> = [["room", "聊天室"], ["members", "群成员"], ["discord", "Discord"]];
  return <div className="room-settings-layer" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="room-settings-drawer" role="dialog" aria-modal="true" aria-label={`${room.session_title} 设置`}>
      <header><div><small>ROOM SETTINGS</small><h2>{room.session_title}</h2></div><button type="button" onClick={onClose} aria-label="关闭设置"><X size={19} /></button></header>
      <nav role="tablist" aria-label="聊天室设置分类">{tabs.map(([value, label]) => <button key={value} type="button" role="tab" aria-selected={tab === value} onClick={() => setTab(value)}>{label}</button>)}</nav>
      <div className="room-settings-content">
        {tab === "room" ? <RoomGeneralSettings room={room} title={title} setTitle={setTitle} summary={summary} setSummary={setSummary} onRefresh={onRefresh} /> : null}
        {tab === "members" ? <RoomMemberSettings room={room} companionMap={companionMap} onRefresh={onRefresh} /> : null}
        {tab === "discord" ? <RoomDiscordSettings room={room} onRefresh={onRefresh} /> : null}
      </div>
    </aside>
  </div>;
}

function RoomGeneralSettings({ room, title, setTitle, summary, setSummary, onRefresh }: {
  room: CompanionRoomBundle; title: string; setTitle: (value: string) => void;
  summary: string; setSummary: (value: string) => void; onRefresh: () => Promise<void>;
}) {
  const [continuation, setContinuation] = useState("");
  const save = useMutation({ mutationFn: () => updateCompanionRoom(room.id, { title: title.trim(), summary: summary.trim() }), onSuccess: onRefresh });
  const archive = useMutation({ mutationFn: () => archiveCompanionRoom(room.id), onSuccess: onRefresh });
  const restore = useMutation({ mutationFn: () => restoreCompanionRoom(room.id, room.roster_revision, "web_room_restore"), onSuccess: onRefresh });
  const successor = useMutation({
    mutationFn: () => createCompanionRoomSuccessor(room.id, {
      title: `${room.session_title} · 下一段`, summary: room.session_summary || undefined,
      continuation_summary: continuation.trim(), confirm_reviewed: true,
      expected_roster_revision: room.roster_revision,
    }),
    onSuccess: result => window.location.assign(`/rooms/${result.session.id}`),
  });
  return <div className="room-settings-section">
    <div className="room-settings-copy"><h3>聊天室信息</h3><p>名称和主题只作用于当前共同空间。</p></div>
    <label><span>群名称</span><input value={title} maxLength={120} onChange={event => setTitle(event.target.value)} disabled={room.session_status !== "active"} /></label>
    <label><span>共同主题</span><textarea rows={4} value={summary} maxLength={1000} onChange={event => setSummary(event.target.value)} disabled={room.session_status !== "active"} /></label>
    {room.session_status === "active" ? <button type="button" className="room-primary-action" disabled={!title.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "正在保存…" : "保存聊天室"}</button> : null}
    {room.session_status === "active" ? <div className="room-successor-control"><h3>按当前成员开启下一段</h3><p>用于上下文变长时继续相处。只携带你在下方明确确认的摘要，不复制原始消息或伙伴私有记忆。</p><textarea rows={4} maxLength={2000} value={continuation} onChange={event => setContinuation(event.target.value)} placeholder="整理并确认希望带到下一段的共同背景…" /><button type="button" disabled={!continuation.trim() || successor.isPending} onClick={() => successor.mutate()}><MessageSquarePlus size={16} />{successor.isPending ? "正在建立下一段…" : "确认摘要并新建"}</button>{successor.isError ? <p className="room-action-error" role="alert">未能建立下一段，请刷新成员 revision 后重试。</p> : null}</div> : null}
    <div className="room-danger-zone"><h3>房间生命周期</h3><p>归档会暂停所有成员并关闭 Shared Scene，但保留历史；恢复会重新验证并激活未撤销成员。</p>{room.session_status === "active" ? <button type="button" disabled={archive.isPending} onClick={() => window.confirm("结束并归档这个聊天室？历史不会删除。") && archive.mutate()}><Archive size={16} />结束并归档</button> : <button type="button" disabled={restore.isPending} onClick={() => restore.mutate()}><RotateCcw size={16} />恢复聊天室</button>}</div>
    {(save.isError || archive.isError || restore.isError) ? <p className="room-action-error" role="alert">操作未完成，请刷新状态后重试。</p> : null}
  </div>;
}

function RoomMemberSettings({ room, companionMap, onRefresh }: {
  room: CompanionRoomBundle; companionMap: Map<string, { id: string; name: string }>; onRefresh: () => Promise<void>;
}) {
  const roster = useCompanionRosterQuery("product", { page: 1, pageSize: 100 });
  const [inviteId, setInviteId] = useState("");
  const [inviteMode, setInviteMode] = useState<"speaker" | "observer">("speaker");
  const [busy, setBusy] = useState("");
  const client = useQueryClient();
  const invite = useMutation({ mutationFn: () => inviteCompanionRoomMember(room.id, { companion_id: inviteId, mode: inviteMode, expected_roster_revision: room.roster_revision }), onSuccess: async () => { setInviteId(""); await onRefresh(); } });
  const transition = async (participant: CoPresenceParticipant, action: "speaker" | "observer" | "mute" | "inactivate" | "reactivate" | "revoke") => {
    setBusy(`${participant.id}:${action}`);
    try {
      await transitionCompanionRoomMember(room.id, participant.id, { action, expected_roster_revision: room.roster_revision, expected_participant_revision: participant.membership_revision });
      await onRefresh();
      await client.invalidateQueries({ queryKey: ["companion-rooms"] });
    } finally { setBusy(""); }
  };
  const historicalIds = new Set(room.participants.flatMap(item => item.participant_companion_id ? [item.participant_companion_id] : []));
  const inviteOptions = (roster.data?.items ?? []).filter(item => !historicalIds.has(item.id));
  const members = room.participants.filter(item => item.participant_type === "companion");
  return <div className="room-settings-section">
    <div className="room-settings-copy"><h3>群成员与模式</h3><p>观察、禁言和未激活都不会被 Coordinator 自动提升为发言者。</p></div>
    <div className="room-member-groups">
      {members.map((member, index) => {
        const companion = companionMap.get(member.participant_companion_id || "");
        const primary = member.participant_companion_id === room.primary_companion_id;
        return <article key={member.id}>
          <CompanionOrb name={companion?.name || "伙伴"} index={index} size="small" />
          <div><strong>{companion?.name || "伙伴"}{primary ? " · 主伙伴" : ""}</strong><small>{memberLabel(member)}</small></div>
          <div className="room-member-actions">
            {member.join_status === "active" ? <><button type="button" title="允许发言" disabled={Boolean(busy)} onClick={() => void transition(member, "speaker")}><Send size={14} /></button><button type="button" title="观察模式" disabled={Boolean(busy)} onClick={() => void transition(member, "observer")}><Eye size={14} /></button><button type="button" title="禁言" disabled={Boolean(busy)} onClick={() => void transition(member, "mute")}><VolumeX size={14} /></button>{!primary ? <button type="button" title="设为未激活" disabled={Boolean(busy)} onClick={() => void transition(member, "inactivate")}><CirclePause size={14} /></button> : null}</> : member.join_status === "inactive" ? <button type="button" title="重新激活" disabled={Boolean(busy)} onClick={() => void transition(member, "reactivate")}><RotateCcw size={14} /></button> : null}
            {!primary && member.join_status !== "revoked" ? <button type="button" className="is-danger" title="踢出并撤销" disabled={Boolean(busy)} onClick={() => window.confirm(`踢出 ${companion?.name || "这位伙伴"}？撤销是终态。`) && void transition(member, "revoke")}><UserMinus size={14} /></button> : null}
          </div>
        </article>;
      })}
    </div>
    <div className="room-invite-control"><label><span>邀请伙伴</span><select value={inviteId} onChange={event => setInviteId(event.target.value)}><option value="">选择尚未加入的伙伴</option>{inviteOptions.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>初始模式</span><select value={inviteMode} onChange={event => setInviteMode(event.target.value as "speaker" | "observer")}><option value="speaker">允许发言</option><option value="observer">观察模式</option></select></label><button type="button" disabled={!inviteId || invite.isPending || room.session_status !== "active"} onClick={() => invite.mutate()}><UserPlus size={16} />邀请</button></div>
    {invite.isError ? <p className="room-action-error" role="alert">邀请失败；已有历史成员请使用“重新激活”。</p> : null}
  </div>;
}

function RoomDiscordSettings({ room, onRefresh }: { room: CompanionRoomBundle; onRefresh: () => Promise<void> }) {
  const [guildRef, setGuildRef] = useState(""); const [guildName, setGuildName] = useState("");
  const [guildId, setGuildId] = useState(room.discord_channel?.guild_id || "");
  const [channelRef, setChannelRef] = useState(""); const [channelName, setChannelName] = useState("");
  const [channelId, setChannelId] = useState(room.discord_channel?.channel_id || "");
  const [selectedBots, setSelectedBots] = useState<string[]>(room.discord_channel?.bot_projections.map(item => item.provider_bot_id) || []);
  const guilds = useQuery({ queryKey: ["discord-room-guilds", room.user_id], queryFn: () => listDiscordRoomGuilds(room.user_id) });
  const channels = useQuery({ queryKey: ["discord-room-channels", room.user_id, guildId], queryFn: () => listDiscordRoomChannels({ user_id: room.user_id, guild_id: guildId || undefined }) });
  const bots = useQuery({ queryKey: ["discord-room-bots", room.user_id], queryFn: () => listDiscordRoomBotIdentities(room.user_id) });
  const ingresses = useQuery({
    queryKey: ["discord-room-ingresses", room.id],
    queryFn: () => listDiscordRoomIngresses(room.id, 20),
    enabled: Boolean(room.discord_channel),
    refetchInterval: room.discord_channel?.binding_status === "active" ? 10_000 : false,
  });
  const createGuild = useMutation({ mutationFn: () => createDiscordRoomGuild({ user_id: room.user_id, provider_guild_ref: guildRef, guild_display_name: guildName }), onSuccess: async item => { setGuildId(item.id); await guilds.refetch(); } });
  const createChannel = useMutation({ mutationFn: () => createDiscordRoomChannel(guildId, { provider_channel_ref: channelRef, channel_display_name: channelName, permission_status: "ready" }), onSuccess: async item => { setChannelId(item.id); await channels.refetch(); } });
  const selectedChannel = channels.data?.items.find(item => item.id === channelId);
  const bind = useMutation({ mutationFn: () => bindDiscordChannelToRoom(channelId, { room_id: room.id, provider_bot_ids: selectedBots, expected_channel_revision: selectedChannel?.revision || 1, expected_room_roster_revision: room.roster_revision, mention_policy: "mention_only" }), onSuccess: onRefresh });
  const transition = useMutation({ mutationFn: (action: "pause" | "resume" | "revoke") => transitionDiscordRoomBinding(room.discord_channel!.id, action, { expected_revision: room.discord_channel!.revision }), onSuccess: onRefresh });
  const activeCompanionIds = new Set(room.participants.filter(item => item.participant_type === "companion" && item.join_status === "active").flatMap(item => item.participant_companion_id ? [item.participant_companion_id] : []));
  const availableBots = bots.data?.items ?? [];
  const mappedIds = new Set(availableBots.filter(item => selectedBots.includes(item.provider_bot_id)).map(item => item.companion_id));
  const exact = selectedBots.length === activeCompanionIds.size && mappedIds.size === activeCompanionIds.size && [...activeCompanionIds].every(id => mappedIds.has(id));
  const toggleBot = (item: DiscordRoomBotIdentity) => setSelectedBots(current => current.includes(item.provider_bot_id) ? current.filter(id => id !== item.provider_bot_id) : [...current, item.provider_bot_id]);
  return <div className="room-settings-section">
    <div className="room-settings-copy"><h3>Discord 频道映射</h3><p>一个文字频道对应一个 Web Room；数量相等仍不足以绑定，伙伴 ID 集合必须完全一致。</p></div>
    {room.discord_channel ? <div className="room-channel-current"><Hash size={17} /><div><strong>{room.discord_channel.guild_display_name} / {room.discord_channel.channel_display_name}</strong><small>{room.discord_channel.binding_status} · {room.discord_channel.mention_policy}</small></div><span>{room.discord_channel.bot_projections.length} 个 Bot</span></div> : null}
    <label><span>Discord 服务器</span><select value={guildId} onChange={event => { setGuildId(event.target.value); setChannelId(""); }}><option value="">选择已登记服务器</option>{guilds.data?.items.map(item => <option key={item.id} value={item.id}>{item.guild_display_name}</option>)}</select></label>
    <details><summary><Plus size={14} />登记服务器</summary><div className="room-inline-form"><input placeholder="Guild ID" value={guildRef} onChange={event => setGuildRef(event.target.value)} /><input placeholder="安全显示名称" value={guildName} onChange={event => setGuildName(event.target.value)} /><button type="button" disabled={!guildRef.trim() || !guildName.trim() || createGuild.isPending} onClick={() => createGuild.mutate()}>登记</button></div></details>
    <label><span>文字频道</span><select value={channelId} disabled={!guildId} onChange={event => setChannelId(event.target.value)}><option value="">选择已登记频道</option>{channels.data?.items.map(item => <option key={item.id} value={item.id}>#{item.channel_display_name} · {item.permission_status}</option>)}</select></label>
    <details><summary><Plus size={14} />登记文字频道</summary><div className="room-inline-form"><input placeholder="Channel ID" value={channelRef} onChange={event => setChannelRef(event.target.value)} /><input placeholder="频道显示名称" value={channelName} onChange={event => setChannelName(event.target.value)} /><button type="button" disabled={!guildId || !channelRef.trim() || !channelName.trim() || createChannel.isPending} onClick={() => createChannel.mutate()}>登记</button></div></details>
    <fieldset className="room-bot-roster"><legend>逻辑参与 Bot</legend>{availableBots.map(item => <label key={item.provider_bot_id}><input type="checkbox" checked={selectedBots.includes(item.provider_bot_id)} onChange={() => toggleBot(item)} /><Bot size={17} /><span><strong>{item.bot_display_name}</strong><small>映射 {item.companion_name}</small></span></label>)}</fieldset>
    <p className={exact ? "room-roster-check is-valid" : "room-roster-check"}><ShieldCheck size={15} />{exact ? "Bot 与当前 active Companion roster 精确一致" : "当前选择尚未通过 Companion ID 集合校验"}</p>
    <button type="button" className="room-primary-action" disabled={!channelId || !exact || bind.isPending} onClick={() => bind.mutate()}>{bind.isPending ? "正在核对并绑定…" : room.discord_channel ? "重新核对绑定" : "建立频道绑定"}</button>
    {room.discord_channel && room.discord_channel.binding_status === "active" ? <button type="button" className="room-secondary-action" disabled={transition.isPending} onClick={() => transition.mutate("pause")}><CirclePause size={16} />暂停频道绑定</button> : room.discord_channel && room.discord_channel.binding_status === "paused" ? <button type="button" className="room-secondary-action" disabled={transition.isPending} onClick={() => transition.mutate("resume")}><RotateCcw size={16} />恢复频道绑定</button> : null}
    {(bind.isError || transition.isError || createGuild.isError || createChannel.isError) ? <p className="room-action-error" role="alert">Discord 映射操作未完成，请检查 revision、权限和精确 roster。</p> : null}
    {room.discord_channel ? <section className="room-channel-evidence" aria-labelledby="room-channel-evidence-title">
      <div><h4 id="room-channel-evidence-title">最近频道同步</h4><small>仅展示结构化状态，不保存 Discord 原始载荷</small></div>
      {ingresses.isLoading ? <p>正在读取耐久同步证据…</p> : ingresses.isError ? <p className="is-error">同步证据暂时无法读取。</p> : ingresses.data?.items.length ? (
        <ol>{ingresses.data.items.map(item => <li key={item.id}>
          <div><strong>{ingressLabel(item.status)}</strong><time>{item.received_at ? formatTime(item.received_at) : "时间待写入"}</time></div>
          <p>{item.mentioned_bot_keys.length ? `点名 ${item.mentioned_bot_keys.join("、")}` : "未点名 Bot，消息仅同步到 Web"}</p>
          <small>{deliverySummary(item.deliveries.map(delivery => delivery.status))}</small>
        </li>)}</ol>
      ) : <p>尚无频道入站记录。下一条 Discord 消息会在这里留下同步与投递状态。</p>}
    </section> : null}
  </div>;
}

function ingressLabel(status: string) {
  if (status === "completed") return "已进入 Room";
  if (status === "suppressed") return "已同步，保持安静";
  if (status === "failed") return "同步失败";
  return "处理中";
}

function deliverySummary(statuses: string[]) {
  if (!statuses.length) return "无 Discord 外发任务";
  const delivered = statuses.filter(status => status === "delivered").length;
  const retrying = statuses.filter(status => status === "queued" || status === "leased" || status === "retry_scheduled").length;
  const failed = statuses.filter(status => status === "failed" || status === "cancelled").length;
  return [`${delivered} 条已投递`, retrying ? `${retrying} 条等待/重试` : "", failed ? `${failed} 条失败/取消` : ""].filter(Boolean).join(" · ");
}

function memberLabel(member: CoPresenceParticipant) {
  if (member.join_status === "revoked") return "已踢出 · 终态";
  if (member.join_status === "inactive") return "未激活 · 不接收新内容";
  if (member.participant_role.includes("observ")) return "观察列表 · 不发言";
  if (!member.can_speak) return "禁言列表 · 不发言";
  return "允许发言列表";
}

function activeSummary(members: CoPresenceParticipant[]) {
  const speakers = members.filter(item => item.join_status === "active" && item.can_speak).length;
  const observers = members.filter(item => item.join_status === "active" && !item.can_speak).length;
  return `${speakers} 位可发言${observers ? ` · ${observers} 位观察/禁言` : ""}`;
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
