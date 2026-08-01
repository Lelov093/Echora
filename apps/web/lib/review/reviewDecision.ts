import type { ReviewInboxReadModel } from "@/lib/api/companionWorkspace";
import { companionWorkspaceApi } from "@/lib/api/companionWorkspace";
import { approveChannelMemoryCandidate, rejectChannelMemoryCandidate } from "@/lib/api/channelGateway";
import { commitGrowth, rejectGrowth } from "@/lib/api/growth";
import { acceptCandidate, commitCandidate, rejectCandidate } from "@/lib/api/memories";
import { decideRealtimeSharedMemoryCandidate } from "@/lib/api/realtimeMemory";
import { relationshipApi } from "@/lib/api/relationships";
import { decideCrossCompanionReview, decidePrivateToSharedReview, decideSharedToPrivateReview } from "@/lib/api/sharedMemory";

export type ReviewInboxItem = ReviewInboxReadModel["items"][number];
export type ReviewDecision = "approve" | "reject";

export async function decideReviewItem(item: ReviewInboxItem, decision: ReviewDecision) {
  if (item.kind === "memory") {
    if (decision === "reject") return rejectCandidate(item.id, { reason: "Rejected from Review Inbox." });
    await acceptCandidate(item.id);
    return commitCandidate(item.id);
  }
  if (item.kind === "growth") return decision === "approve" ? commitGrowth(item.id) : rejectGrowth(item.id, { reason: "Rejected from Review Inbox." });
  if (item.kind === "relationship") {
    if (decision === "reject") return relationshipApi.reject(item.companion_id, item.id);
    const page = await relationshipApi.candidates(item.companion_id, "pending");
    const candidate = page.items.find((value) => value.id === item.id);
    if (!candidate) throw new Error("关系候选已变化，请刷新后重试。");
    return relationshipApi.commit(item.companion_id, candidate);
  }
  if (item.kind === "private_to_shared") return decidePrivateToSharedReview(item.id, { decision: decision === "approve" ? "approved" : "rejected", review_reason: "Decided from Review Inbox." });
  if (item.kind === "shared_to_private") return decideSharedToPrivateReview(item.id, { decision: decision === "approve" ? "approved" : "rejected", review_reason: "Decided from Review Inbox." });
  if (item.kind === "cross_companion") return decideCrossCompanionReview(item.id, { decision: decision === "approve" ? "approved" : "rejected", review_reason: "Decided from Review Inbox." });
  if (item.kind === "channel") return decision === "approve" ? approveChannelMemoryCandidate(item.id, { review_notes: "Approved from Review Inbox." }) : rejectChannelMemoryCandidate(item.id, { review_notes: "Rejected from Review Inbox." });
  if (item.kind === "persona_growth") return companionWorkspaceApi.decidePersonaGrowth(item.companion_id, item.id, decision === "approve" ? "approved" : "rejected");
  if (item.kind === "realtime_shared") return decideRealtimeSharedMemoryCandidate(item.id, decision === "approve" ? "approved" : "rejected");
  throw new Error("当前运行基线尚未提供此审核类型的安全决策接口。");
}
