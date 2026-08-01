"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { getSettings, updateSettings } from "@/lib/api/settings";

export function MemoryPolicySettings({ companionId }: { companionId: string }) {
  const client = useQueryClient();
  const queryKey = ["presence-policy", companionId];
  const policy = useQuery({ queryKey, queryFn: () => getSettings(companionId) });
  const save = useMutation({
    mutationFn: (form: FormData) => {
      const memoryPolicy = String(form.get("memory_save_policy") || "review_important");
      return updateSettings(companionId, {
        memory_save_policy: memoryPolicy,
        sensitive_memory_policy: String(form.get("sensitive_memory_policy") || "always_review"),
        allow_auto_memory_low_risk: memoryPolicy === "auto_low_risk",
        allow_sensitive_memory_without_review: false,
      });
    },
    onSuccess: (value) => client.setQueryData(queryKey, value),
    onError: () => void policy.refetch(),
  });

  if (policy.isLoading) return <section className="memory-policy-state">正在读取记忆保存策略…</section>;
  if (!policy.data || policy.isError) return <section className="memory-policy-state is-error"><p>暂时无法读取记忆保存策略。</p><button type="button" onClick={() => void policy.refetch()}>重试</button></section>;
  const value = policy.data;
  return <form key={String(value.updated_at || value.id)} className="memory-policy-settings" onSubmit={(event) => { event.preventDefault(); save.mutate(new FormData(event.currentTarget)); }}>
    <header><ShieldCheck size={19} /><div><small>记忆保存边界</small><h2>决定什么需要你的确认</h2><p>这是记忆策略的唯一写入口。共享、跨伙伴、频道与敏感内容不会因为自动化模式而绕过审核。</p></div></header>
    <p className="settings-ownership-note">这里决定“是否形成或保留记忆”；伙伴档案中的<Link href={`/settings/companions/${companionId}/profile`}>可见性策略</Link>只决定“已经存在的内容可以被谁读取”，Conversation 的临时/跨会话设置只影响一段对话。</p>
    <div>
      <label><span>一般记忆</span><select name="memory_save_policy" defaultValue={String(value.memory_save_policy || "review_important")}><option value="review_all">全部确认</option><option value="review_important">重要变化确认</option><option value="auto_low_risk">仅低风险私有记忆自动保存</option></select><small>自动保存只适用于当前伙伴的严格低风险私有记忆。</small></label>
      <label><span>敏感内容</span><select name="sensitive_memory_policy" defaultValue={String(value.sensitive_memory_policy || "always_review")}><option value="always_review">始终确认</option><option value="never_save">不保存</option><option value="allow_with_warning">警示后形成候选</option></select><small>任何选项都不会允许敏感内容无审核直接写入。</small></label>
    </div>
    <footer><span>Automation 只决定支持范围内的参与程度，不拥有这些领域规则。</span><button type="submit" disabled={save.isPending}>{save.isPending ? "正在保存…" : "保存记忆策略"}</button></footer>
    {save.isSuccess ? <p role="status">记忆策略已保存。</p> : null}{save.isError ? <p role="alert">保存冲突或失败，已重新读取最新策略。</p> : null}
  </form>;
}
