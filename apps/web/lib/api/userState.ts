import { api } from "./client";

// Detail-level API client.
// Reserved for future user-state detail drawers.
// Do not remove: contract is validated by backend smoke tests.

export interface UserStateSnapshot {
  id: string;
  signal_type: string;
  observed_value: number;
  smoothed_value: number;
  smoothing_factor: number;
  confidence: number;
  mode_key?: string | null;
  reason?: string | null;
  created_at?: string | null;
}

export function getUserStateSnapshot(snapshotId: string) {
  return api.get<UserStateSnapshot>(`/user-state/snapshots/${snapshotId}`);
}

export function listUserStateSnapshots(companionId?: string, signalType?: string) {
  const params: Record<string, string> = {};
  if (companionId) params.companion_id = companionId;
  if (signalType) params.signal_type = signalType;
  const qs = Object.keys(params).length ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<{ items: UserStateSnapshot[]; total: number }>(`/user-state/snapshots${qs}`);
}

export function listUserStateForUser(userId: string) {
  return api.get<{ items: UserStateSnapshot[] }>(`/users/${userId}/state/snapshots`);
}
