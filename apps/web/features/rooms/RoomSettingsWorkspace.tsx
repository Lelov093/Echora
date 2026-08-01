"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Bot,
  CircleAlert,
  Hash,
  MessageSquarePlus,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { DataState } from "@/components/patterns/DataState";
import { SettingsViewHeader } from "@/components/settings/SettingsView";
import {
  listCoPresenceSessions,
  listDiscordRoomBotIdentities,
  listDiscordRoomChannels,
  listDiscordRoomGuilds,
} from "@/lib/api/coPresence";
import { useCompanionRosterQuery } from "@/lib/queries/companions";
import type { DiscordChannelProjection, DiscordRoomBindingProjection } from "@/lib/types";

const ROOM_PAGE_SIZE = 100;

export function RoomSettingsWorkspace() {
  const roster = useCompanionRosterQuery("product", { page: 1, pageSize: 1 });
  const ownerId = roster.data?.items[0]?.user_id || "";
  const rooms = useQuery({
    queryKey: ["companion-rooms", "settings", ownerId],
    queryFn: () => listCoPresenceSessions({
      user_id: ownerId,
      scope: "product",
      session_source: "companion_home",
      page: 1,
      page_size: ROOM_PAGE_SIZE,
    }),
    enabled: Boolean(ownerId),
  });
  const guilds = useQuery({
    queryKey: ["companion-room-guilds", "settings", ownerId],
    queryFn: () => listDiscordRoomGuilds(ownerId),
    enabled: Boolean(ownerId),
  });
  const channels = useQuery({
    queryKey: ["companion-room-channels", "settings", ownerId],
    queryFn: () => listDiscordRoomChannels({ user_id: ownerId }),
    enabled: Boolean(ownerId),
  });
  const bots = useQuery({
    queryKey: ["companion-room-bots", "settings", ownerId],
    queryFn: () => listDiscordRoomBotIdentities(ownerId),
    enabled: Boolean(ownerId),
  });

  if (roster.isLoading || (ownerId && rooms.isLoading)) {
    return <DataState kind="loading" title="正在读取聊天室设置" description="正在核对 Room、成员与 Discord 映射。" />;
  }
  if (roster.isError || (ownerId && rooms.isError)) {
    return <DataState kind="error" title="聊天室设置暂时不可用" description="无法读取真实 Room 列表，请确认 8010 服务与数据库状态。" />;
  }

  const roomItems = rooms.data?.items ?? [];
  const channelItems = channels.data?.items ?? [];
  const bindingByRoom = new Map<string, { channel: DiscordChannelProjection; binding: DiscordRoomBindingProjection }>();
  for (const channel of channelItems) {
    if (channel.binding) bindingByRoom.set(channel.binding.room_id, { channel, binding: channel.binding });
  }
  const activeRooms = roomItems.filter((room) => room.session_status === "active").length;
  const liveBindings = channelItems.filter((channel) => channel.binding && channel.binding.binding_status !== "revoked").length;
  const conflictBindings = channelItems.filter((channel) => channel.binding?.binding_status === "conflict_paused").length;
  const channelDataPartial = guilds.isLoading || channels.isLoading || bots.isLoading || guilds.isError || channels.isError || bots.isError;

  return (
    <main className="settings-native-view room-settings-workspace">
      <SettingsViewHeader
        eyebrow="设置 / 交互与能力"
        title="聊天室"
        description="集中查看共同空间、成员模式和 Discord Channel 映射；具体房间操作仍在对应聊天室内完成。"
        icon={UsersRound}
        aside={<><strong>多伙伴聊天室</strong><p>多伙伴独立回复已接通；跨伙伴共享仍默认待确认，观察者不会自动发言。</p></>}
      />

      <section className="room-settings-metrics" aria-label="聊天室状态概览">
        <Metric label="聊天室" value={roomItems.length} detail={`${activeRooms} 个进行中`} />
        <Metric label="频道绑定" value={liveBindings} detail={conflictBindings ? `${conflictBindings} 个冲突暂停` : "无 roster 冲突"} tone={conflictBindings ? "warning" : "normal"} />
        <Metric label="可用 Bot 身份" value={bots.data?.items.length ?? 0} detail={`${guilds.data?.items.length ?? 0} 个 Guild · ${channelItems.length} 个频道`} />
      </section>

      {channelDataPartial ? <p className="room-settings-partial" role="status"><CircleAlert size={15} />Discord 映射数据仍在加载或部分不可用；Room 真值不受影响。</p> : null}

      <section className="room-settings-list-section">
        <header>
          <div><small>ROOM MANAGEMENT</small><h2>共同空间</h2><p>从这里进入具体聊天室，继续管理名称、成员模式、生命周期和频道绑定。</p></div>
          <Link href="/?mode=multi&create_room=1"><MessageSquarePlus size={17} />新建聊天室</Link>
        </header>
        {roomItems.length ? <div className="room-settings-list">{roomItems.map((room) => {
          const companions = room.participants.filter((participant) => participant.participant_type === "companion");
          const activeSpeakers = companions.filter((participant) => participant.join_status === "active" && participant.can_speak).length;
          const observers = companions.filter((participant) => participant.join_status === "active" && !participant.can_speak).length;
          const mapped = bindingByRoom.get(room.id);
          return <article key={room.id}>
            <div className="room-settings-room-icon"><UsersRound size={19} /></div>
            <div className="room-settings-room-copy">
              <div><h3>{room.session_title}</h3><StatusPill status={room.session_status} /></div>
              <p>{room.session_summary || "暂时没有共同主题。"}</p>
              <small>{companions.length} 位伙伴 · {activeSpeakers} 位可发言 · {observers} 位观察/禁言</small>
            </div>
            <div className="room-settings-binding">
              {mapped ? <><span className={`is-${mapped.binding.binding_status}`}><Hash size={14} />{mapped.channel.channel_display_name}</span><small>{bindingLabel(mapped.binding.binding_status)} · {mapped.binding.bot_projections.length} 个 Bot 映射</small></> : <><span><ShieldCheck size={14} />仅 Web</span><small>尚未绑定 Discord Channel</small></>}
            </div>
            <Link className="room-settings-open" href={`/rooms/${room.id}?settings=1`} aria-label={`打开 ${room.session_title} 的具体设置`}><span>具体设置</span><ArrowUpRight size={16} /></Link>
          </article>;
        })}</div> : <div className="room-settings-empty"><UsersRound size={28} /><h3>还没有聊天室</h3><p>先选择真实 Companion 建立一个共同空间。</p><Link href="/?mode=multi&create_room=1">创建聊天室</Link></div>}
      </section>

      <section className="room-settings-boundaries" aria-label="聊天室通用边界">
        <header><small>ROOM-WIDE BOUNDARIES</small><h2>所有聊天室共同遵循</h2></header>
        <div>
          <article><ShieldCheck size={18} /><h3>共享仍需确认</h3><p>Shared、cross-Companion 与 channel memory 默认 review-gated，不复制任何伙伴的私有记忆。</p></article>
          <article><UsersRound size={18} /><h3>成员模式不会漂移</h3><p>Observer 不会自动成为 speaker；inactive 和 revoked 成员不会接收后续 Room 内容。</p></article>
          <article><Bot size={18} /><h3>Bot 只是渠道投影</h3><p>Discord 绑定必须精确匹配 Companion ID 集合，数量相同但身份不同会被拒绝。</p></article>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value, detail, tone = "normal" }: { label: string; value: number; detail: string; tone?: "normal" | "warning" }) {
  return <article className={tone === "warning" ? "is-warning" : undefined}><small>{label}</small><strong>{value}</strong><span>{detail}</span></article>;
}

function StatusPill({ status }: { status: string }) {
  return <span className={`room-settings-status is-${status}`}>{status === "active" ? "进行中" : status === "ended" ? "已归档" : status}</span>;
}

function bindingLabel(status: string) {
  if (status === "active") return "绑定有效";
  if (status === "paused") return "已暂停";
  if (status === "conflict_paused") return "成员冲突，已暂停";
  return "已撤销";
}
