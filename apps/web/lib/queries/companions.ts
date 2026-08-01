"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { listCompanions } from "@/lib/api/companions";
import { companionWorkspaceApi } from "@/lib/api/companionWorkspace";
import type { CompanionBundle } from "@/lib/types";

export const companionKeys = {
  roster: (scope: string, page?: number, pageSize?: number, search?: string) => ["companions", "roster", scope, page, pageSize, search] as const,
  workspace: (companionId: string) => ["companions", companionId, "workspace"] as const,
};

export function useCompanionRosterQuery(scope = "product", options: { page?: number; pageSize?: number; search?: string } = {}) {
  const page = options.page ?? 1;
  const pageSize = options.pageSize ?? 100;
  const search = options.search?.trim() ?? "";
  return useQuery({
    queryKey: companionKeys.roster(scope, page, pageSize, search),
    queryFn: () => listCompanions({ scope, page, page_size: pageSize, search: search || undefined }),
  });
}

export function useCompanionWorkspaceQuery(companionId: string) {
  return useQuery({ queryKey: companionKeys.workspace(companionId), queryFn: () => companionWorkspaceApi.workspace(companionId), enabled: Boolean(companionId) });
}

export function companionHousehold(items: CompanionBundle[], companionId?: string) {
  const anchor = items.find((item) => item.id === companionId) ?? items[0];
  return anchor ? items.filter((item) => item.user_id === anchor.user_id) : [];
}

export function useCompanionReviewTotal(companionId?: string) {
  const roster = useCompanionRosterQuery();
  const companions = companionHousehold(roster.data?.items ?? [], companionId).slice(0, 6);
  const workspaces = useQueries({ queries: companions.map((companion) => ({
    queryKey: companionKeys.workspace(companion.id),
    queryFn: () => companionWorkspaceApi.workspace(companion.id),
    staleTime: 30_000,
  })) });
  return workspaces.reduce((total, query) => total + (query.data?.review_counts.total ?? 0), 0);
}
