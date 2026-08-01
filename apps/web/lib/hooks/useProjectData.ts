"use client";

import { useCallback } from "react";
import { listProjectMilestones, listProjectTasks } from "@/lib/api/projects";
import { usePaginatedData } from "@/lib/hooks/usePaginatedData";

export function useProjectMilestones(pageSize = 25) {
  const loader = useCallback(() => listProjectMilestones({ page_size: pageSize }), [pageSize]);
  return usePaginatedData(loader);
}

export function useProjectTasks(status?: string, pageSize = 25) {
  const loader = useCallback(
    () => listProjectTasks({ status, page_size: pageSize }),
    [status, pageSize],
  );
  return usePaginatedData(loader);
}
