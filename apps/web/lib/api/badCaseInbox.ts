import { api, queryString, type QueryParams } from "./client";
import type { BadCaseInboxItem, PaginatedItems } from "@/lib/types";

export interface BadCaseLink {
  id: string;
  bad_case_inbox_item_id: string;
  link_type: string;
  linked_id?: string | null;
  relation: string;
  note?: string | null;
}

export function listBadCaseInboxItems(params?: QueryParams) {
  return api.get<PaginatedItems<BadCaseInboxItem>>(`/bad-case-inbox${queryString(params)}`);
}
export function createBadCaseInboxItem(data: Partial<BadCaseInboxItem>) {
  return api.post<BadCaseInboxItem>("/bad-case-inbox", data);
}
export function getBadCaseInboxItem(id: string) {
  return api.get<BadCaseInboxItem>(`/bad-case-inbox/${id}`);
}
export function updateBadCaseInboxItem(id: string, data: Partial<BadCaseInboxItem>) {
  return api.patch<BadCaseInboxItem>(`/bad-case-inbox/${id}`, data);
}
export function triageBadCaseInboxItem(id: string, data: Record<string, unknown>) {
  return api.post<BadCaseInboxItem>(`/bad-case-inbox/${id}/triage`, data);
}
export function createBadCaseInboxLink(id: string, data: Partial<BadCaseLink>) {
  return api.post<BadCaseLink>(`/bad-case-inbox/${id}/links`, data);
}
export function convertInboxItemToBadCase(id: string, data?: Record<string, unknown>) {
  return api.post(`/bad-case-inbox/${id}/bad-case`, data);
}
export function convertInboxItemToRegressionCase(id: string, data?: Record<string, unknown>) {
  return api.post(`/bad-case-inbox/${id}/regression-case`, data);
}
