import { DataState } from "@/components/patterns/DataState";

export function EmptyState({ title, description }: { icon?: string; title: string; description?: string }) {
  return <DataState kind="empty" title={title} description={description} />;
}
