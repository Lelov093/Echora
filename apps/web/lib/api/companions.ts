import { apiGet, apiPatch, apiPost, queryString, type QueryParams } from "./client";
import type { CompanionBundle, PaginatedItems } from "@/lib/types";

export function listCompanions(params?: QueryParams) {
  return apiGet<PaginatedItems<CompanionBundle>>(`/companions${queryString(params)}`);
}

export function createCompanion(data: Record<string, unknown>) {
  return apiPost<CompanionBundle>("/companions", data);
}

export function getCompanion(companionId: string) {
  return apiGet<CompanionBundle>(`/companions/${companionId}`);
}

export function updateCompanion(companionId: string, data: Record<string, unknown>) {
  return apiPatch<CompanionBundle>(`/companions/${companionId}`, data);
}

export const getHub = (cid: string) => apiGet(`/companions/${cid}/hub`);
export const getModes = (cid: string) => apiGet<PaginatedItems<{ id: string; mode_key: string; display_name: string; is_enabled: boolean }>>(`/companions/${cid}/modes`);
export const switchMode = (cid: string, key: string) => apiPost<CompanionBundle>(`/companions/${cid}/modes/${key}/switch`);
