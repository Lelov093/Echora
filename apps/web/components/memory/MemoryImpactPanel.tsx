"use client";

import { MessageCircle, Radio, Sparkles } from "lucide-react";
import { useMemoryImpact } from "@/lib/hooks/useMemoryImpact";
import { DataState } from "@/components/patterns/DataState";

interface Props {
  memoryId: string | null;
}

export function MemoryImpactPanel({ memoryId }: Props) {
  const { data, loading, error } = useMemoryImpact(memoryId);

  if (!memoryId) {
    return <DataState kind="empty" title="请选择一条记忆" description="查看它怎样参与回复、成长与主动陪伴。" />;
  }

  if (loading) {
    return <DataState kind="loading" title="正在读取影响" />;
  }

  if (error) {
    return <DataState kind="error" title="暂时无法读取这条记忆的影响" description={error} />;
  }

  if (!data) {
    return null;
  }

  const { overview } = data;

  return (
    <div className="memory-impact-summary">
      <p>{impactDescription(overview.strength, overview.confidence)}</p>
      <div>
        <span><MessageCircle size={15} />参与回复<strong>{overview.used_in_responses} 次</strong></span>
        <span><Sparkles size={15} />参与成长<strong>{overview.used_in_growth} 次</strong></span>
        <span><Radio size={15} />参与 Presence<strong>{overview.used_in_presence} 次</strong></span>
      </div>
      <small>反馈会继续调整它未来被召回的机会；淡化、锁定、归档与恢复都从记忆页完成。</small>
    </div>
  );
}

function impactDescription(strength: number, confidence: number) {
  if (strength >= 0.75 && confidence >= 0.75) return "这是一条影响较强、可信程度较高的记忆，可能明显参与伙伴的回复、成长判断和主动联系。";
  if (strength >= 0.45) return "这条记忆会在话题相关时自然参与互动，但不会覆盖更新、更明确的纠正。";
  return "这条记忆目前只作轻微参考，除非被重新确认或在后续互动中再次出现。";
}
