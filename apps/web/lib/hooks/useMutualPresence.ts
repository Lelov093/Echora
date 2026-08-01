"use client";

import { usePresenceQueue } from "./usePresenceQueue";
import {
  acceptOpportunity,
  dismissOpportunity,
  listMutualPresenceOpportunities,
  snoozeOpportunity,
  suppressOpportunityType,
} from "@/lib/api/mutualPresence";

export function useMutualPresence() {
  const base = usePresenceQueue();
  return {
    ...base,
    list: listMutualPresenceOpportunities,
    acceptOpportunity,
    dismissOpportunity,
    snoozeOpportunity,
    suppressOpportunityType,
  };
}
