export const settingsSurfacePrefixes = [
  "/settings",
] as const;

export const retiredProductEntries = [
  { source: "/companions", destination: "/?mode=single", disposition: "redirected" },
  { source: "/companions/[companion_id]", destination: "/?mode=single&companion_id=…", disposition: "redirected" },
  { source: "/conversation", destination: "/companions/[companion_id]/conversations/[conversation_id]", disposition: "scoped_entry" },
  { source: "/scenes", destination: "/?mode=multi", disposition: "redirected" },
] as const;

export const retainedDeepCapabilityRoutes = [
  "/co-presence",
  "/memory/shared",
  "/memory/realtime-buffer",
  "/memory/channel-candidates",
  "/presence/resident",
  "/realtime",
  "/realtime/sessions/[id]",
  "/realtime/voice",
  "/scenes/[scene_id]",
  "/trace/realtime",
  "/trace/realtime/replay",
  "/trace/channel-audit",
] as const;

export function isSettingsProductSurface(pathname: string) {
  return settingsSurfacePrefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}
