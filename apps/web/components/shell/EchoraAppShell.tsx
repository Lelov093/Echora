"use client";

import { Suspense } from "react";
import { usePathname } from "next/navigation";
import { UnifiedSettingsShell } from "@/components/settings/UnifiedSettingsShell";
import { isSettingsProductSurface } from "@/lib/navigation/productSurfaces";

export function EchoraAppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isImmersiveConversation = /^\/companions\/[^/]+\/conversations\/[^/]+$/.test(pathname);
  const settingsSurface = isSettingsProductSurface(pathname);

  return (
    <div className={`echora-refoundation-shell${isImmersiveConversation ? " is-immersive-conversation" : ""}`}>
      <a className="echora-skip-link" href="#echora-main-content">跳到主要内容</a>
      <main id="echora-main-content" className="echora-refoundation-main">{settingsSurface && !isImmersiveConversation ? <Suspense fallback={<div className="unified-settings-loading">正在恢复设置导航…</div>}><UnifiedSettingsShell>{children}</UnifiedSettingsShell></Suspense> : children}</main>
    </div>
  );
}
