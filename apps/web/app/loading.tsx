import { DataState } from "@/components/patterns/DataState";

export default function Loading() {
  return <DataState kind="loading" title="正在抵达这里" description="正在同步伙伴状态与边界信息。" />;
}
