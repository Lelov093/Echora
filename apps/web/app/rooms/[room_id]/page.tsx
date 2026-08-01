import { CompanionRoomWorkspace } from "@/features/rooms/CompanionRoomWorkspace";
import "../../../styles/companion-room-workspace.css";

export default async function CompanionRoomPage({ params }: { params: Promise<{ room_id: string }> }) {
  const { room_id } = await params;
  return <CompanionRoomWorkspace roomId={room_id} />;
}
