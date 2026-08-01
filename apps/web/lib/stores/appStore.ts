"use client";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export const DEFAULT_COMPANION_ID = "87089684-d2e7-4022-9638-251302a93ef4";
export const ALL_COMPANIONS_ID = "__all_companions__";

interface UIState {
  activeCompanionId: string | null;
  hydrated: boolean;
  sessionRailOpen: boolean;
  contextDrawerOpen: boolean;
  globalSearchOpen: boolean;
  traceDrawerOpen: boolean;
  traceRunId: string | null;
  rightPanelTab: string;
  setActiveCompanionId: (companionId: string | null) => void;
  setHydrated: (hydrated: boolean) => void;
  setSessionRailOpen: (open: boolean) => void;
  setContextDrawerOpen: (open: boolean) => void;
  setGlobalSearchOpen: (open: boolean) => void;
  setTraceDrawer: (open: boolean, traceId?: string) => void;
  setRightPanelTab: (tab: string) => void;
}
export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      activeCompanionId: null,
      hydrated: false,
      sessionRailOpen: true,
      contextDrawerOpen: true,
      globalSearchOpen: false,
      traceDrawerOpen: false,
      traceRunId: null,
      rightPanelTab: "memories",
      setActiveCompanionId: (companionId) => set({ activeCompanionId: companionId }),
      setHydrated: (hydrated) => set({ hydrated }),
      setSessionRailOpen: (sessionRailOpen) => set({ sessionRailOpen }),
      setContextDrawerOpen: (contextDrawerOpen) => set({ contextDrawerOpen }),
      setGlobalSearchOpen: (globalSearchOpen) => set({ globalSearchOpen }),
      setTraceDrawer: (open, traceId) => set({ traceDrawerOpen: open, traceRunId: traceId ?? null }),
      setRightPanelTab: (tab) => set({ rightPanelTab: tab }),
    }),
    {
      name: "echora-ui-state",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        activeCompanionId: state.activeCompanionId,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
    },
  ),
);
