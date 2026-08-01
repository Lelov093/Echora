"use client";

type ListControlsProps = {
  query: string;
  onQueryChange: (value: string) => void;
  status: string;
  onStatusChange: (value: string) => void;
  statuses?: string[];
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  sort?: string;
  onSortChange?: (value: string) => void;
  sortOptions?: Array<{ value: string; label: string }>;
  label?: string;
};

export function ListControls({
  query,
  onQueryChange,
  status,
  onStatusChange,
  statuses = ["all"],
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  sort,
  onSortChange,
  sortOptions,
  label = "List controls",
}: ListControlsProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="list-controls glass-soft" aria-label={label}>
      <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="搜索当前列表" aria-label="搜索当前列表" />
      <select value={status} onChange={(event) => onStatusChange(event.target.value)} aria-label="状态筛选">
        {statuses.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}
      </select>
      {sortOptions && onSortChange && (
        <select value={sort} onChange={(event) => onSortChange(event.target.value)} aria-label="排序方式">
          {sortOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      )}
      <select value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))} aria-label="每页数量">
        {[10, 20, 50].map((size) => <option key={size} value={size}>每页 {size} 条</option>)}
      </select>
      <div className="list-controls-pages">
        <button type="button" className="act-btn" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>上一页</button>
        <span>第 {page} / {pageCount} 页 · 共 {total} 条</span>
        <button type="button" className="act-btn" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>下一页</button>
      </div>
    </section>
  );
}

function statusLabel(value: string) {
  return ({
    all: "全部状态",
    pending: "待确认",
    candidate: "候选",
    committed: "已确认",
    rejected: "已拒绝",
    reverted: "已撤回",
    active: "生效中",
    invalidated: "已失效",
    corrected: "已纠正",
    completed: "已完成",
    failed: "失败",
  } as Record<string, string>)[value] ?? value;
}
