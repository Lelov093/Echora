import GrowthPageBody from "@/components/page-bodies/GrowthPageBody";
import { SettingsViewHeader } from "@/components/settings/SettingsView";
import { Sparkles } from "lucide-react";

export function OrbitalGrowthPage() {
  return (
    <div className="settings-native-view orbital-domain-growth-workspace">
      <SettingsViewHeader eyebrow="设置 / 伙伴" title="成长与理解" description="查看伙伴如何形成新的理解、核对证据，并决定接受、拒绝或回滚。" icon={Sparkles} aside={<><strong>始终需要你的确认</strong><p>成长候选不会因为视觉迁移而自动写入。</p></>} />
      <div className="orbital-domain-page-body"><GrowthPageBody /></div>
    </div>
  );
}
