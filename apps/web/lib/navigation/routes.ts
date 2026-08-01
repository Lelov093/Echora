export type RouteNavItem = {
  href: string;
  label: string;
  description?: string;
  activePaths?: Array<string | RouteMatch>;
  match?: "exact" | "prefix";
  badge?: string;
};

export type RouteMatch = {
  path: string;
  match?: "exact" | "prefix";
};

function normalizePath(pathname: string) {
  if (pathname.length > 1 && pathname.endsWith("/")) return pathname.slice(0, -1);
  return pathname;
}

function getMatches(item: RouteNavItem): RouteMatch[] {
  const source = item.activePaths ?? [{ path: item.href, match: item.match ?? "exact" }];
  return source.map((entry) => typeof entry === "string" ? { path: entry, match: item.match ?? "prefix" } : entry);
}

function matchScore(pathname: string, item: RouteNavItem) {
  const normalized = normalizePath(pathname);
  let best = -1;
  for (const entry of getMatches(item)) {
    const path = normalizePath(entry.path);
    const strategy = entry.match ?? item.match ?? "exact";
    const matched = strategy === "exact"
      ? normalized === path
      : path === "/" ? normalized === "/" : normalized === path || normalized.startsWith(`${path}/`);
    if (matched) {
      best = Math.max(best, path.length + (strategy === "exact" ? 1000 : 0));
    }
  }
  return best;
}

export function getActiveNavHref(pathname: string, items: RouteNavItem[]) {
  let winner: { href: string; score: number } | null = null;
  for (const item of items) {
    const score = matchScore(pathname, item);
    if (score >= 0 && (!winner || score > winner.score)) {
      winner = { href: item.href, score };
    }
  }
  return winner?.href ?? null;
}

export function isRouteNavItemActive(pathname: string, item: RouteNavItem, items?: RouteNavItem[]) {
  if (items) return getActiveNavHref(pathname, items) === item.href;
  return matchScore(pathname, item) >= 0;
}

export const companionNavItems: RouteNavItem[] = [
  { href: "/companions", label: "Roster", description: "All companion identities" },
  { href: "/co-presence", label: "Co-Presence", description: "Shared companion sessions" },
  { href: "/scenes", label: "Shared Scenes", description: "共同经历场景" },
];

export const presenceNavItems: RouteNavItem[] = [
  { href: "/presence", label: "Presence Queue", description: "Everyday presence opportunities", match: "exact" },
  { href: "/presence/resident", label: "Resident Presence", description: "Availability, budgets, silence", match: "prefix" },
  { href: "/realtime", label: "Realtime", description: "SSE co-presence sessions", match: "exact" },
  { href: "/realtime/voice", label: "Voice Readiness", description: "Readiness only", match: "prefix" },
];

export const memoryNavItems: RouteNavItem[] = [
  { href: "/memory", label: "Control Center", description: "Private memory garden and review lane", match: "exact" },
  { href: "/memory/shared", label: "Shared Memory", description: "Review-gated shared episodes", match: "prefix" },
  { href: "/memory/realtime-buffer", label: "Realtime Buffer", description: "Ephemeral realtime candidates", match: "prefix" },
  { href: "/memory/channel-candidates", label: "Channel Candidates", description: "External channel review gate", match: "prefix", badge: "Gateway" },
];

export const traceNavItems: RouteNavItem[] = [
  { href: "/trace", label: "Overview", description: "Trace surfaces and audit entrypoints", match: "exact" },
  { href: "/trace/realtime", label: "Realtime Trace", description: "Permission and memory-gate evidence", match: "exact" },
  { href: "/trace/realtime/replay", label: "Realtime Replay", description: "Redacted event replay", match: "prefix" },
  { href: "/trace/channel-audit", label: "Channel Audit", description: "Discord and gateway delivery audit", match: "prefix", badge: "Gateway" },
];

export const agentLabNavItems: RouteNavItem[] = [
  { href: "/projects", label: "Projects", description: "Project contexts and tasks" },
  { href: "/tools", label: "Tools", description: "Tool contracts and runs" },
  { href: "/bad-cases", label: "Bad Cases", description: "Regression inbox" },
  { href: "/evaluation", label: "Evaluation", description: "Eval suites and runs" },
  { href: "/replays", label: "Replays", description: "Replay center" },
];

export const settingsNavItems: RouteNavItem[] = [
  { href: "/settings", label: "Boundaries", description: "Memory, presence, and safety policy", match: "exact" },
  { href: "/settings/channels/discord", label: "Discord Setup", description: "Multi-bot identities and companion binding", match: "prefix", badge: "Discord" },
  { href: "/settings/tools", label: "Tools", description: "Tool runtime and Companion permissions", match: "prefix" },
  { href: "/settings/system/data-privacy", label: "Data & Privacy", description: "Retention and data-rights preflight", match: "prefix" },
];
