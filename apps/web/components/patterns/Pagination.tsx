"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { PaginatedItems } from "@/lib/types";

export const DETAIL_PAGE_SIZE = 8;

export function usePageParam(name = "page") {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const raw = Number(searchParams.get(name) ?? 1);
  const page = Number.isInteger(raw) && raw > 0 ? raw : 1;

  function setPage(nextPage: number) {
    const params = new URLSearchParams(searchParams.toString());
    if (nextPage <= 1) params.delete(name);
    else params.set(name, String(nextPage));
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  return [page, setPage] as const;
}

export function Pagination({
  pagination,
  page,
  onPageChange,
  disabled = false,
}: {
  pagination?: PaginatedItems<unknown>["pagination"];
  page: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
}) {
  if (!pagination || pagination.total_pages <= 1) return null;
  const current = Math.min(page, pagination.total_pages);

  return (
    <nav className="detail-pagination" aria-label="列表分页">
      <span>共 {pagination.total} 条 · 第 {current}/{pagination.total_pages} 页</span>
      <div>
        <button type="button" onClick={() => onPageChange(current - 1)} disabled={disabled || current <= 1}>上一页</button>
        <button type="button" onClick={() => onPageChange(current + 1)} disabled={disabled || current >= pagination.total_pages}>下一页</button>
      </div>
    </nav>
  );
}
