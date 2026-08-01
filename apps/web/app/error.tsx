"use client";

import { DataState } from "@/components/patterns/DataState";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <DataState kind="error" title="这部分暂时没有连接上" description="你的数据没有被改动，可以重新尝试。" action={<button className="echora-state-action" onClick={reset}>重新尝试</button>} />;
}
