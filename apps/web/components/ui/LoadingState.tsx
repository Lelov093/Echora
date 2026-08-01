import { DataState } from "@/components/patterns/DataState";

export function LoadingState({ text = "Loading..." }: { text?: string }) {
  return <DataState kind="loading" title={text} />;
}
