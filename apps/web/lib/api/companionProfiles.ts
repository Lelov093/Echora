import { api } from "./client";

export const companionProfilesApi = {
  identity: (id: string) => api.get<Record<string, unknown>>(`/companions/${id}/identity`),
  persona: (id: string) => api.get<Record<string, unknown>>(`/companions/${id}/persona`),
  contract: (id: string) => api.get<Record<string, unknown>>(`/companions/${id}/contract`),
  boundary: (id: string) => api.get<Record<string, unknown>>(`/companions/${id}/boundary`),
  visibility: (id: string) => api.get<Record<string, unknown>>(`/companions/${id}/visibility`),
  patchOwnerSettings: (id: string, body: Record<string, unknown>) => api.patch<Record<string, unknown>>(`/companions/${id}/owner-settings`, body),
  archive: (id: string, body: Record<string, unknown>) => api.post<Record<string, unknown>>(`/companions/${id}/archive`, body),
  restore: (id: string, body: Record<string, unknown>) => api.post<Record<string, unknown>>(`/companions/${id}/restore`, body),
  patchVisibility: (id: string, body: Record<string, unknown>) => api.patch<Record<string, unknown>>(`/companions/${id}/visibility`, body),
};
