"use client";

import { useMemo, useState } from "react";

type UseClientListControlsOptions<T> = {
  items: T[];
  searchText: (item: T) => string;
  status?: (item: T) => string | null | undefined;
  sort?: (items: T[], sortKey: string) => T[];
  initialPageSize?: number;
  initialSort?: string;
};

export function useClientListControls<T>({
  items,
  searchText,
  status,
  sort,
  initialPageSize = 10,
  initialSort = "updated_desc",
}: UseClientListControlsOptions<T>) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const [sortKey, setSortKey] = useState(initialSort);

  const statuses = useMemo(() => {
    const found = new Set<string>(["all"]);
    if (status) {
      items.forEach((item) => {
        const value = status(item);
        if (value) found.add(value);
      });
    }
    return Array.from(found);
  }, [items, status]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let next = items.filter((item) => {
      const statusOk = statusFilter === "all" || status?.(item) === statusFilter;
      const queryOk = !q || searchText(item).toLowerCase().includes(q);
      return statusOk && queryOk;
    });
    if (sort) next = sort(next, sortKey);
    return next;
  }, [items, query, searchText, sort, sortKey, status, statusFilter]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const pageItems = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  return {
    query,
    setQuery: (value: string) => {
      setQuery(value);
      setPage(1);
    },
    status: statusFilter,
    setStatus: (value: string) => {
      setStatusFilter(value);
      setPage(1);
    },
    statuses,
    page: safePage,
    setPage,
    pageSize,
    setPageSize: (value: number) => {
      setPageSizeState(value);
      setPage(1);
    },
    sortKey,
    setSortKey,
    total: filtered.length,
    filtered,
    pageItems,
  };
}
