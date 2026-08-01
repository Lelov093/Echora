"use client";

import { useCallback, useEffect, useState } from "react";

interface UsePaginatedDataOptions<T> {
  enabled?: boolean;
  initialItems?: T[];
}

interface PaginationState {
  page: number;
  page_size: number;
  total: number;
}

export function usePaginatedData<T>(
  loader: () => Promise<{ items: T[]; page?: number; page_size?: number; total?: number } | { items?: T[]; page?: number; page_size?: number; total?: number }>,
  options: UsePaginatedDataOptions<T> = {},
) {
  const [items, setItems] = useState<T[]>(() => options.initialItems ?? []);
  const [pagination, setPagination] = useState<PaginationState>({ page: 1, page_size: options.initialItems?.length || 0, total: options.initialItems?.length || 0 });
  const [loading, setLoading] = useState(Boolean(options.enabled ?? true));
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (options.enabled === false) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await loader();
      setItems(result.items ?? []);
      setPagination({
        page: result.page ?? 1,
        page_size: result.page_size ?? (result.items?.length ?? 0),
        total: result.total ?? (result.items?.length ?? 0),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [loader, options.enabled]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => {
    load();
  }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return { items, pagination, loading, error, reload: load };
}
