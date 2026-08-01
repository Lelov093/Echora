"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

type HomePaginationProps = {
  label: string;
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (page: number) => void;
};

export function HomePagination({ label, page, totalPages, total, onPageChange }: HomePaginationProps) {
  if (totalPages <= 1) return null;
  return (
    <nav className="home-pagination" aria-label={label}>
      <button type="button" onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label={`${label}上一页`}>
        <ChevronLeft size={17} aria-hidden="true" />
      </button>
      <span aria-live="polite"><strong>{page}</strong> / {totalPages}<small>共 {total} 项</small></span>
      <button type="button" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages} aria-label={`${label}下一页`}>
        <ChevronRight size={17} aria-hidden="true" />
      </button>
    </nav>
  );
}
