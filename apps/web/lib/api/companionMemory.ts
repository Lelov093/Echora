import { apiGet } from "./client";
import type { CompanionMemoryRecord, PaginatedItems } from "@/lib/types";

export interface CompanionMemoryQuery {
  state?: string;
  scope_type?: string;
  page?: number;
  page_size?: number;
}

export function listCompanionMemories(companionId: string, params?: CompanionMemoryQuery) {
  const qs = params ? `?${new URLSearchParams(Object.entries(params).reduce<Record<string, string>>((acc, [key, value]) => {
    if (value !== undefined && value !== null && value !== "") acc[key] = String(value);
    return acc;
  }, {})).toString()}` : "";
  return apiGet<PaginatedItems<CompanionMemoryRecord>>(`/companions/${companionId}/memories${qs}`);
}
