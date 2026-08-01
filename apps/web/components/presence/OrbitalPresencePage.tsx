import PresencePageBody from "@/components/page-bodies/PresencePageBody";
import { SettingsViewHeader } from "@/components/settings/SettingsView";
import { Radio } from "lucide-react";

export function OrbitalPresencePage() {
  return (
    <div className="settings-native-view orbital-domain-presence-workspace">
      <SettingsViewHeader eyebrow="设置 / 伙伴" title="Presence 与安静陪伴" description="管理主动联系、延后、抑制与 meaningful silence；安静始终是一种有效决定。" icon={Radio} aside={<><strong>Quiet-first</strong><p>Hard stop、revoke、quiet hours 与 focus mode 始终优先。</p></>} />
      <div className="orbital-domain-page-body"><PresencePageBody /></div>
    </div>
  );
}
