import { apiGet } from "./client";

export interface HubCompanion {
  id?: string;
  name?: string;
  current_mode?: string;
  current_status?: string;
  current_focus?: string;
}

export interface HubStats {
  active_memories?: number;
  pending_memory_candidates?: number;
  pending_growth_candidates?: number;
  queued_presence_opportunities?: number;
}

export interface HubContinuity {
  conversation_id?: string;
  current_topic?: string;
  current_goal?: string;
  open_threads?: string[];
  last_message_at?: string;
}

export interface HubMemory {
  id?: string;
  summary?: string;
  content?: string;
  type?: string;
  state?: string;
  memory_strength?: number;
  updated_at?: string;
  created_at?: string;
}

export interface HubPresence {
  id?: string;
  title?: string;
  reason?: string;
  message?: string;
  status?: string;
}

export interface HubData {
  companion: HubCompanion;
  stats: HubStats;
  last_continuity: HubContinuity;
  recent_memories: HubMemory[];
  presence_preview: HubPresence[];
}

export const fetchHub = (companionId: string) => apiGet<HubData>(`/companions/${companionId}/hub`);
