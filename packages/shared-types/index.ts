// ── Echora Shared Types ─────────────────────────────────────────────
// Shared product type definitions.
// Based on: docs/Echora 全局类型与枚举字典 V1.txt

// ── Global Primitives ───────────────────────────────────────────────

export type UUID = string;
export type Timestamp = string;
export type JsonObject = Record<string, unknown>;
export type JsonArray = unknown[];

// ── API Envelope ────────────────────────────────────────────────────

export type ApiResponseStatus = "success" | "error" | "partial_success";

export interface ApiError {
  code: string;
  message: string;
  details?: JsonObject;
}

export interface ApiMeta {
  timestamp?: string;
  page?: number;
  page_size?: number;
  total?: number;
}

export interface ApiResponse<T = unknown> {
  data: T | null;
  error: ApiError | null;
  meta: ApiMeta | null;
}

// ── Entity Lifecycle ────────────────────────────────────────────────

export type EntityLifecycleStatus = "active" | "archived" | "deleted" | "disabled";

// ── Mode ────────────────────────────────────────────────────────────

export type ModeKey =
  | "project"
  | "creative"
  | "daily"
  | "learning"
  | "game"
  | "character"
  | "virtual_world";

// ── Conversation / Message ──────────────────────────────────────────

export type ConversationStatus = "active" | "paused" | "archived" | "deleted";

export type MessageRole = "user" | "assistant" | "system" | "tool";

export type MessageSource =
  | "text"
  | "voice_input"
  | "screen_context"
  | "image_context"
  | "file_context"
  | "device_event"
  | "tool_result"
  | "system";

// ── Memory ──────────────────────────────────────────────────────────

export type MemoryLayer =
  | "global"
  | "mode"
  | "session"
  | "project"
  | "creative"
  | "daily"
  | "learning"
  | "game"
  | "character"
  | "virtual_world";

export type MemoryScope =
  | "global"
  | "mode"
  | "conversation"
  | "session"
  | "project"
  | "character"
  | "virtual_world"
  | "auraweave_context"
  | "personal_branch";

export type MemoryStatus = "active" | "suppressed" | "outdated" | "archived" | "deleted";

export type MemoryCandidateStatus =
  | "pending_review"
  | "accepted"
  | "rejected"
  | "edited"
  | "committed"
  | "expired"
  | "discarded";

// ── Review ──────────────────────────────────────────────────────────

export type ReviewItemType =
  | "memory_candidate"
  | "growth_candidate"
  | "presence_opportunity";

export type ReviewStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "edited"
  | "committed"
  | "expired"
  | "discarded";

export type ReviewDecision = "accept" | "reject" | "edit" | "commit" | "defer" | "discard";

// ── Presence ────────────────────────────────────────────────────────

export type PresenceOpportunityStatus =
  | "pending"
  | "shown"
  | "suppressed"
  | "deferred"
  | "dismissed"
  | "acted"
  | "expired"
  | "blocked";

export type PresenceChannelType =
  | "hub"
  | "queue"
  | "inline";

// ── Trace ───────────────────────────────────────────────────────────

export type TraceRunStatus =
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "replayed";

export type TraceStepStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped"
  | "cancelled";

export type TraceStepType =
  | "input"
  | "mode_router"
  | "memory_retrieval"
  | "response_planning"
  | "response_generation"
  | "memory_candidate"
  | "growth_candidate"
  | "presence_opportunity"
  | "boundary_check"
  | "review_commit";

// ── Growth ──────────────────────────────────────────────────────────

export type GrowthCandidateStatus =
  | "pending_review"
  | "accepted"
  | "rejected"
  | "edited"
  | "committed"
  | "expired";

export type GrowthDimension =
  | "preference_understanding"
  | "communication_style"
  | "project_context"
  | "creative_context"
  | "learning_context"
  | "daily_rhythm"
  | "relationship_continuity"
  | "boundary_awareness";

// ── Feedback ────────────────────────────────────────────────────────

export type FeedbackEventType =
  | "thumbs_up"
  | "thumbs_down"
  | "too_much"
  | "too_little"
  | "wrong_memory"
  | "wrong_mode"
  | "wrong_tone"
  | "wrong_presence"
  | "bad_timing"
  | "helpful"
  | "not_helpful"
  | "manual_note";

// ── Common Error Codes ──────────────────────────────────────────────

export type CommonErrorCode =
  | "BAD_REQUEST"
  | "UNAUTHORIZED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "CONFLICT"
  | "VALIDATION_ERROR"
  | "RATE_LIMITED"
  | "INTERNAL_ERROR"
  | "NOT_IMPLEMENTED";
