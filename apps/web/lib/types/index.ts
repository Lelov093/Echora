/** Echora frontend type definitions.

Shared product types for the Echora web application.
New shared contracts should be aligned with the shared-types package.
*/

// ── Primitives ──────────────────────────────────────────────────────

export type UUID = string;
export type Timestamp = string;

// ── API Envelope ────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiMeta {
  request_id?: string;
  elapsed_ms?: number;
}

export interface ApiResponse<T = unknown> {
  data: T | null;
  error: ApiError | null;
  meta: ApiMeta | Record<string, unknown> | null;
}

export interface PaginatedItems<T> {
  items: T[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

// ── Domain Types ────────────────────────────────────────────────────

export type ModeKey =
  | "project" | "creative" | "daily" | "learning"
  | "game" | "character" | "virtual_world";

export type MemoryType =
  | "fact" | "preference" | "goal" | "episodic" | "correction"
  | "relationship" | "emotional" | "self" | "project" | "creative" | "system";

export type MemoryState = "active" | "dormant" | "archived" | "suppressed" | "deleted";
export type ConversationStatus = "active" | "paused" | "archived" | "deleted";
export type MessageRole = "user" | "assistant" | "system" | "tool";

// Domain data primitives
export type DomainRecordStatus = string;
export type RiskLevel = "low" | "medium" | "high" | "critical";
export type LearningMode = "disabled" | "shadow" | "assistive" | "active";
export type JsonObject = Record<string, unknown>;

export interface DomainBaseRecord {
  id: UUID;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
  metadata?: JsonObject;
}

export interface ToolDefinition extends DomainBaseRecord {
  name: string;
  display_name?: string | null;
  description?: string | null;
  tool_type: string;
  risk_level: RiskLevel;
  permission_policy: string;
  is_enabled?: boolean;
  status: DomainRecordStatus;
  input_schema_json?: JsonObject;
}

export interface FileDocument extends DomainBaseRecord {
  file_source_id?: UUID | null;
  title: string;
  document_type: string;
  status: DomainRecordStatus;
  chunk_count?: number;
}

export interface ProjectTask extends DomainBaseRecord {
  milestone_id?: UUID | null;
  title: string;
  status: DomainRecordStatus;
  priority?: number;
  evidence_summary?: string | null;
}

export interface AgentRunReplay extends DomainBaseRecord {
  trace_run_id?: UUID | null;
  replay_type: string;
  status: DomainRecordStatus;
  title?: string | null;
  summary?: string | null;
  trace_snapshot_json?: JsonObject;
}

export interface BadCaseInboxItem extends DomainBaseRecord {
  source_type: string;
  case_type: string;
  severity: string;
  status: DomainRecordStatus;
  title: string;
  description?: string | null;
  trace_run_id?: UUID | null;
  replay_id?: UUID | null;
}

export interface EvaluationRun extends DomainBaseRecord {
  dataset_id?: UUID | null;
  status: DomainRecordStatus;
  judge_type: string;
  aggregate_score?: number | null;
}

export interface RegressionCase extends DomainBaseRecord {
  source_bad_case_id?: UUID | null;
  source_replay_id?: UUID | null;
  title: string;
  case_type: string;
  expected_behavior: string;
  status: DomainRecordStatus;
}

export interface LlmProviderConfig extends DomainBaseRecord {
  provider_name: string;
  provider_type: string;
  status: DomainRecordStatus;
  base_url?: string | null;
  env_key_name?: string | null;
  config_json?: JsonObject;
}

export interface EvidenceSufficiencyEvent extends DomainBaseRecord {
  target_type: string;
  target_id?: UUID | null;
  sufficiency_score: number;
  status: DomainRecordStatus;
  evidence_refs?: JsonObject[];
  explanation?: string | null;
}

// Companion and co-presence primitives
export type CompanionRelationshipRole = string;
export type CompanionPresenceStyle = string;
export type MemoryParticipationMode = string;

export interface CompanionBundle {
  id: UUID;
  user_id: UUID;
  name: string;
  subtitle?: string | null;
  identity_prompt?: string | null;
  base_personality?: string | null;
  tone_profile: JsonObject;
  companion_profile: JsonObject;
  current_mode: string;
  current_status: string;
  current_focus?: string | null;
  companion_environment?: "unclassified" | "product" | "test";
  provenance?: string;
  identity_profile_status?: string | null;
  persona_lock_level?: string | null;
  relationship_role?: CompanionRelationshipRole | null;
  boundary_scope?: string | null;
  created_at?: Timestamp | null;
    updated_at?: Timestamp | null;
    first_meeting_conversation_id?: UUID;
  }

export interface CompanionIdentityProfile {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  display_name: string;
  identity_summary: string;
  origin_story?: string | null;
  self_continuity_summary?: string | null;
  core_traits_json: unknown[];
  identity_labels_json: unknown[];
  voice_style_hint?: string | null;
  avatar_style_hint?: string | null;
  profile_status: string;
  created_at: Timestamp;
  updated_at: Timestamp;
}

export interface CompanionPersonaProfile {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  persona_summary: string;
  communication_style_summary?: string | null;
  tone_descriptors_json: unknown[];
  core_values_json: unknown[];
  response_preferences_json: JsonObject;
  persona_lock_level: string;
  drift_guard_level: string;
  presence_style: CompanionPresenceStyle;
  created_at: Timestamp;
  updated_at: Timestamp;
}

export interface CompanionRelationshipContract {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  relationship_role: CompanionRelationshipRole;
  contract_status: string;
  contract_summary: string;
  collaboration_style_summary?: string | null;
  support_scope_json: unknown[];
  shared_memory_policy: string;
  cross_companion_disclosure_policy: string;
  contract_json: JsonObject;
  created_at: Timestamp;
  updated_at: Timestamp;
}

export interface CompanionBoundaryProfile {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  boundary_json: JsonObject;
  private_memory_default: string;
  shared_memory_default: string;
  global_memory_read_scope: string;
  cross_companion_read_policy: string;
  review_required_private_to_shared: boolean;
  review_required_shared_to_private: boolean;
  review_required_cross_companion_share: boolean;
  presence_interrupt_policy: string;
  created_at: Timestamp;
  updated_at: Timestamp;
}

export interface CompanionVisibilityPolicy {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  memory_visibility_policy: string;
  user_global_memory_scope: string;
  relationship_memory_scope: string;
  allow_low_risk_summary_read: boolean;
  allow_authorized_global_read: boolean;
  allow_sensitive_global_read: boolean;
  allow_other_companion_private_read: boolean;
  visibility_rules_json: JsonObject;
  created_at: Timestamp;
  updated_at: Timestamp;
}

export interface CompanionLifecycleEvent {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  event_type: string;
  event_source: string;
  title?: string | null;
  detail?: string | null;
  previous_state_json: JsonObject;
  new_state_json: JsonObject;
  review_required: boolean;
  occurred_at: Timestamp;
  created_at: Timestamp;
}

export interface CompanionMemoryRecord {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  owner_companion_id?: UUID | null;
  shared_memory_id?: UUID | null;
  memory_scope_type: string;
  type: string;
  state: string;
  visibility: string;
  consent_status: string;
  content: string;
  summary: string;
  importance?: number | null;
  confidence?: number | null;
  memory_strength?: number | null;
  visibility_policy_json: JsonObject;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface SharedEpisodicMemory {
  id: UUID;
  user_id: UUID;
  title?: string | null;
  summary: string;
  content: string;
  status: string;
  source_type: string;
  visibility_policy_json: JsonObject;
  scene_context_json: JsonObject;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface SharedMemoryCandidate {
  id: UUID;
  user_id: UUID;
  source_memory_candidate_id?: UUID | null;
  source_memory_id?: UUID | null;
  proposed_shared_memory_id?: UUID | null;
  source_shared_experience_record_id?: UUID | null;
  title?: string | null;
  summary: string;
  content: string;
  candidate_status: string;
  requires_user_review: boolean;
  candidate_policy_json: JsonObject;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface PrivateToSharedMemoryReview {
  id: UUID;
  user_id: UUID;
  source_companion_id: UUID;
  memory_id: UUID;
  shared_memory_candidate_id?: UUID | null;
  target_shared_memory_id?: UUID | null;
  decision: string;
  review_reason?: string | null;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface SharedToPrivateMemoryReview {
  id: UUID;
  user_id: UUID;
  target_companion_id: UUID;
  shared_memory_id: UUID;
  target_memory_id?: UUID | null;
  decision: string;
  review_reason?: string | null;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface CrossCompanionMemoryEvent {
  id: UUID;
  user_id: UUID;
  source_companion_id: UUID;
  target_companion_id: UUID;
  memory_id?: UUID | null;
  shared_memory_id?: UUID | null;
  event_type: string;
  status: string;
  reason?: string | null;
  review_required: boolean;
  policy_json: JsonObject;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface CrossCompanionMemoryReview {
  id: UUID;
  user_id: UUID;
  cross_companion_memory_event_id: UUID;
  decision: string;
  review_reason?: string | null;
  approved_policy_json: JsonObject;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface CoPresenceSessionPolicy {
  id: UUID;
  co_presence_session_id: UUID;
  policy_status: string;
  default_primary_memory_participation: MemoryParticipationMode;
  default_active_memory_participation: MemoryParticipationMode;
  default_observing_memory_participation: MemoryParticipationMode;
  default_delegated_memory_participation: MemoryParticipationMode;
  user_global_memory_scope: string;
  cross_companion_private_read_policy: string;
  private_to_shared_policy: string;
  shared_to_private_policy: string;
  allow_observing_companion_long_term_memory: boolean;
  allow_autonomous_companion_interaction: boolean;
  session_visibility_policy_json: JsonObject;
  boundary_policy_json: JsonObject;
}

export interface ParticipantAwarenessState {
  id: UUID;
  user_id: UUID;
  co_presence_session_id: UUID;
  participant_id: UUID;
  target_participant_id?: UUID | null;
  awareness_type: string;
  awareness_level: string;
  awareness_status: string;
  updated_by_source: string;
  awareness_summary?: string | null;
  awareness_json: JsonObject;
  updated_at: Timestamp;
}

export interface ParticipantMemoryPermission {
  id: UUID;
  user_id: UUID;
  co_presence_session_id: UUID;
  participant_id: UUID;
  permission_source: string;
  memory_participation_override?: MemoryParticipationMode | null;
  allow_private_candidate?: boolean | null;
  allow_shared_candidate?: boolean | null;
  allow_user_global_summary_read?: boolean | null;
  allow_user_global_full_read?: boolean | null;
  allow_cross_companion_private_read?: boolean | null;
  allow_private_to_shared_sync?: boolean | null;
  allow_shared_to_private_sync?: boolean | null;
  review_required: boolean;
  boundary_policy_json: JsonObject;
}

export interface CoPresenceParticipant {
  id: UUID;
  user_id: UUID;
  co_presence_session_id: UUID;
  participant_type: string;
  participant_role: string;
  participant_user_id?: UUID | null;
  participant_companion_id?: UUID | null;
  external_agent_label?: string | null;
  join_status: string;
  visibility_scope: string;
  can_speak: boolean;
  can_delegate: boolean;
  joined_at?: Timestamp | null;
  left_at?: Timestamp | null;
  rejoined_at?: Timestamp | null;
  muted_at?: Timestamp | null;
  revoked_at?: Timestamp | null;
  membership_revision: number;
  policy_override_json: JsonObject;
  awareness_states: ParticipantAwarenessState[];
  memory_permission?: ParticipantMemoryPermission | null;
}

export interface CoPresenceSessionBundle {
  id: UUID;
  user_id: UUID;
  primary_companion_id: UUID;
  originating_conversation_id?: UUID | null;
  session_title: string;
  session_summary?: string | null;
  session_status: string;
  session_source: string;
  visibility_scope: string;
  entry_reason?: string | null;
  participant_summary_json: JsonObject;
  boundary_summary_json: JsonObject;
  started_at?: Timestamp | null;
  ended_at?: Timestamp | null;
  roster_revision: number;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
  policy?: CoPresenceSessionPolicy | null;
  participants: CoPresenceParticipant[];
  shared_scene_ids: UUID[];
}

export interface CompanionRoomMembershipEvent {
  id: UUID;
  participant_id?: UUID | null;
  companion_id: UUID;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  from_role?: string | null;
  to_role?: string | null;
  roster_revision: number;
  participant_revision: number;
  reason?: string | null;
  occurred_at?: Timestamp | null;
}

export interface DiscordBotProjection {
  membership_id: UUID;
  provider_bot_id: UUID;
  bot_display_name: string;
  companion_id: UUID;
  companion_name: string;
  participation_mode: string;
  membership_status: string;
  identity_revision: number;
}

export interface DiscordRoomBindingProjection {
  id: UUID;
  room_id: UUID;
  channel_id: UUID;
  channel_display_name?: string | null;
  channel_ref_hash_prefix?: string | null;
  guild_id?: UUID | null;
  guild_display_name?: string | null;
  binding_status: string;
  mention_policy: string;
  roster_fingerprint: string;
  room_roster_revision: number;
  revision: number;
  bot_projections: DiscordBotProjection[];
}

export interface CompanionRoomBundle extends CoPresenceSessionBundle {
  conversation?: { id: UUID; title: string; status: string; companion_id: UUID } | null;
  membership_events: CompanionRoomMembershipEvent[];
  discord_channel?: DiscordRoomBindingProjection | null;
  runtime_status: "multi_companion_active";
  composer_enabled: boolean;
}

export interface CompanionRoomMessage {
  id: UUID;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  content_format: string;
  companion_id: UUID;
  companion_name: string;
  model_provider?: string | null;
  model_name?: string | null;
  metadata: JsonObject;
  created_at: Timestamp;
}

export interface CompanionRoomTurnStep {
  id: UUID;
  companion_id: UUID;
  companion_name: string;
  participant_id: UUID;
  ordinal: number;
  status: "planned" | "running" | "completed" | "suppressed" | "failed" | "cancelled";
  selection_reason: string;
  attempt_count: number;
  trace_run_id?: UUID | null;
  assistant_message_id?: UUID | null;
  evidence: JsonObject;
  error: JsonObject;
  retry_available_at?: Timestamp | null;
  lease_expires_at?: Timestamp | null;
  completed_at?: Timestamp | null;
}

export interface CompanionRoomTurn {
  id: UUID;
  room_id: UUID;
  conversation_id: UUID;
  user_message_id: UUID;
  idempotency_key: string;
  source: string;
  status: "planning" | "running" | "completed" | "partial_failed" | "suppressed" | "failed" | "cancelled";
  cancellation_requested: boolean;
  speaker_plan: JsonObject;
  result: JsonObject;
  error: JsonObject;
  revision: number;
  steps: CompanionRoomTurnStep[];
  started_at?: Timestamp | null;
  completed_at?: Timestamp | null;
  idempotent_replay: boolean;
}

export interface DiscordGuildProjection {
  id: UUID;
  user_id: UUID;
  guild_display_name: string;
  guild_ref_hash_prefix: string;
  guild_status: string;
  revision: number;
}

export interface DiscordChannelProjection {
  id: UUID;
  guild_id: UUID;
  channel_display_name: string;
  channel_ref_hash_prefix: string;
  channel_status: string;
  permission_status: string;
  revision: number;
  binding?: DiscordRoomBindingProjection | null;
}

export interface DiscordRoomBotIdentity {
  provider_bot_id: UUID;
  bot_key: string;
  bot_display_name: string;
  companion_channel_identity_id: UUID;
  identity_revision: number;
  companion_id: UUID;
  companion_name: string;
}

export interface DiscordChannelDeliveryProjection {
  id: UUID;
  companion_id: UUID;
  assistant_message_id: UUID;
  trace_run_id?: UUID | null;
  status: "queued" | "leased" | "retry_scheduled" | "delivered" | "failed" | "cancelled";
  attempt_count: number;
  max_attempts: number;
  next_attempt_at?: Timestamp | null;
  delivered_at?: Timestamp | null;
  last_error_code?: string | null;
  last_error_summary?: string | null;
}

export interface DiscordChannelIngressProjection {
  id: UUID;
  room_id: UUID;
  conversation_id: UUID;
  room_turn_id?: UUID | null;
  user_message_id?: UUID | null;
  status: "received" | "processing" | "completed" | "partial_failed" | "suppressed" | "failed" | "ignored";
  mentioned_bot_keys: string[];
  selected_companion_ids: UUID[];
  evidence: JsonObject;
  error: JsonObject;
  deliveries: DiscordChannelDeliveryProjection[];
  received_at?: Timestamp | null;
  completed_at?: Timestamp | null;
  idempotent_replay: boolean;
}

export interface SharedSceneEvent {
  id: UUID;
  shared_scene_id: UUID;
  co_presence_session_id?: UUID | null;
  participant_id?: UUID | null;
  event_type: string;
  event_source: string;
  title: string;
  content?: string | null;
  visibility_scope: string;
  triggers_shared_experience_candidate: boolean;
  event_payload_json: JsonObject;
  occurred_at?: Timestamp | null;
}

export interface SharedExperienceRecord {
  id: UUID;
  co_presence_session_id?: UUID | null;
  shared_scene_id?: UUID | null;
  source_scene_event_id?: UUID | null;
  source_type: string;
  experience_title?: string | null;
  experience_summary: string;
  experience_detail?: string | null;
  experience_status: string;
  recommended_memory_action: string;
  review_required: boolean;
  created_by_participant_id?: UUID | null;
  policy_snapshot_json: JsonObject;
  occurred_at?: Timestamp | null;
}

export interface SharedSceneBundle {
  id: UUID;
  user_id: UUID;
  co_presence_session_id?: UUID | null;
  owner_companion_id?: UUID | null;
  scene_title: string;
  scene_summary?: string | null;
  scene_type: string;
  scene_status: string;
  source_type: string;
  focal_topic?: string | null;
  visibility_scope: string;
  context_json: JsonObject;
  visibility_policy_json: JsonObject;
  opened_at?: Timestamp | null;
  closed_at?: Timestamp | null;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
  participants: Array<{
    id: UUID;
    participant_type: string;
    participant_role: string;
    name: string;
    join_status: string;
    visibility_scope: string;
    can_speak: boolean;
    can_delegate: boolean;
  }>;
  events: SharedSceneEvent[];
  shared_experiences: SharedExperienceRecord[];
}

export interface DelegatedExecutionIntentRecord {
  trace_run_id: UUID;
  conversation_id?: UUID | null;
  user_id?: UUID | null;
  requested_by_companion_id?: UUID | null;
  co_presence_session_id?: UUID | null;
  shared_scene_id?: UUID | null;
  task_title: string;
  task_summary: string;
  status: string;
  executor_type?: string | null;
  tool_constraints?: JsonObject;
  memory_boundary_json?: JsonObject;
  boundary_check?: JsonObject;
  linked_tool_run_id?: UUID | null;
  linked_project_task_id?: UUID | null;
  inspection_summary?: string | null;
  shared_experience_record_id?: UUID | null;
  shared_experience_status?: string | null;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
  metadata?: JsonObject;
}

// Realtime compatibility primitives
export type RealtimeTransport = "sse" | string;

export interface RealtimeCoPresenceParticipant {
  id: UUID;
  user_id: UUID;
  realtime_session_id: UUID;
  co_presence_participant_id?: UUID | null;
  participant_type: string;
  participant_role: string;
  participant_status: string;
  participant_user_id?: UUID | null;
  participant_companion_id?: UUID | null;
  external_agent_label?: string | null;
  can_listen: boolean;
  can_speak: boolean;
  can_observe: boolean;
  can_remember: boolean;
  can_receive_transcript: boolean;
  permission_snapshot_json: JsonObject;
  runtime_state_json: JsonObject;
  joined_at?: Timestamp | null;
  left_at?: Timestamp | null;
}

export interface RealtimeSessionChannel {
  id: UUID;
  user_id: UUID;
  realtime_session_id: UUID;
  channel_type: string;
  channel_status: string;
  transport_type: RealtimeTransport;
  is_default_event_stream: boolean;
  can_send_events: boolean;
  can_receive_actions: boolean;
  permission_snapshot_json: JsonObject;
  runtime_state_json: JsonObject;
  opened_at?: Timestamp | null;
  closed_at?: Timestamp | null;
  last_event_at?: Timestamp | null;
}

export interface RealtimeSessionStateEvent {
  id: UUID;
  event_type: string;
  event_status: string;
  previous_status?: string | null;
  next_status?: string | null;
  event_payload_json: JsonObject;
  occurred_at?: Timestamp | null;
}

export interface RealtimeCoPresenceSessionBundle {
  id: UUID;
  user_id: UUID;
  co_presence_session_id?: UUID | null;
  active_companion_id?: UUID | null;
  originating_conversation_id?: UUID | null;
  shared_scene_id?: UUID | null;
  session_title?: string | null;
  session_status: string;
  session_source: string;
  default_transport: RealtimeTransport;
  permission_snapshot_json: JsonObject;
  participant_summary_json: JsonObject;
  boundary_snapshot_json: JsonObject;
  runtime_state_json: JsonObject;
  participants: RealtimeCoPresenceParticipant[];
  channels: RealtimeSessionChannel[];
  recent_state_events: RealtimeSessionStateEvent[];
  started_at?: Timestamp | null;
  paused_at?: Timestamp | null;
  ended_at?: Timestamp | null;
  last_event_at?: Timestamp | null;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface RealtimeChannelEvent {
  id: UUID;
  realtime_session_id?: UUID | null;
  channel_id?: UUID | null;
  event: string;
  event_type?: string;
  event_status?: string;
  payload: JsonObject;
  preview?: string | null;
  occurred_at?: Timestamp | null;
}

export interface CompanionVoiceSessionBundle extends DomainBaseRecord {
  user_id: UUID;
  realtime_session_id: UUID;
  co_presence_session_id?: UUID | null;
  speaker_companion_id: UUID;
  speaker_realtime_participant_id?: UUID | null;
  voice_profile_id?: UUID | null;
  session_status: string;
  transcript_retention_policy: string;
  memory_write_policy: string;
  allow_multi_speaker: boolean;
  permission_snapshot_json: JsonObject;
  voice_runtime_json: JsonObject;
  turns: JsonObject[];
  stt_events: JsonObject[];
  tts_events: JsonObject[];
  turn_taking_events: JsonObject[];
  interruptions: JsonObject[];
  persona_guard_runs: JsonObject[];
}

export interface MultimodalContextEventBundle extends DomainBaseRecord {
  user_id: UUID;
  realtime_session_id?: UUID | null;
  co_presence_session_id?: UUID | null;
  shared_scene_id?: UUID | null;
  source_participant_id?: UUID | null;
  context_type: string;
  context_source: string;
  context_status: string;
  raw_data_ref?: string | null;
  raw_data_retention_policy: string;
  raw_data_storage_allowed: boolean;
  retention_policy_json: JsonObject;
  permission_snapshot_json: JsonObject;
  visibility_summary_json: JsonObject;
  redaction_status: string;
  expires_at?: Timestamp | null;
  permissions: JsonObject[];
  retention?: JsonObject | null;
}

export interface RealtimeMemoryBufferBundle extends DomainBaseRecord {
  user_id: UUID;
  realtime_session_id?: UUID | null;
  co_presence_session_id?: UUID | null;
  shared_scene_id?: UUID | null;
  owner_companion_id?: UUID | null;
  buffer_scope: string;
  buffer_status: string;
  default_memory_action: string;
  retention_policy: string;
  review_required: boolean;
  auto_write_private_memory: boolean;
  auto_write_shared_memory: boolean;
  buffer_summary?: string | null;
  policy_snapshot_json: JsonObject;
  items: JsonObject[];
  companion_private_buffers: JsonObject[];
  copresence_buffers: JsonObject[];
  shared_scene_buffers: JsonObject[];
}

export interface ResidentStatusRecord {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  realtime_session_id?: UUID | null;
  status_type: string;
  status_source: string;
  interruption_level: string;
  allows_unsolicited_presence: boolean;
  presence_summary?: string | null;
  policy_snapshot_json: JsonObject;
  occurred_at?: Timestamp | null;
}

export interface PresenceBudgetEvaluation {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  budget_scope: string;
  budget_status: string;
  enforcement_policy: string;
  max_presence_minutes: number;
  used_presence_minutes: number;
  max_interruptions: number;
  used_interruptions: number;
  budget_policy_json: JsonObject;
  decision: string;
  allowed: boolean;
}

export interface CoPresenceInvitationRecord {
  id: UUID;
  user_id: UUID;
  realtime_session_id?: UUID | null;
  inviter_companion_id?: UUID | null;
  target_companion_id?: UUID | null;
  invitation_status: string;
  invitation_source: string;
  requires_user_approval: boolean;
  auto_join_allowed: boolean;
  memory_candidate_allowed: boolean;
  invitation_reason?: string | null;
  policy_snapshot_json: JsonObject;
  expires_at?: Timestamp | null;
}

export interface MeaningfulSilenceResult {
  quiet: JsonObject;
  focus: JsonObject;
}

export interface ScopedHardStopResult {
  hard_stop: JsonObject & { id?: UUID; hard_stop_scope?: string; requires_audit?: boolean };
  audit: JsonObject;
}

export interface RealtimeTraceV5Detail {
  summary: JsonObject;
  realtime_trace_session: JsonObject | null;
  events: JsonObject[];
  participant_event_traces: JsonObject[];
  speaker_traces: JsonObject[];
  permission_audits: JsonObject[];
  memory_gate_traces: JsonObject[];
  replay: JsonObject | null;
  replay_segments: JsonObject[];
  redactions: JsonObject[];
  hard_stop_audits: JsonObject[];
  trace_steps: JsonObject[];
}

export interface ChannelGatewayReadinessContract {
  api_available: boolean;
  connector_implementation: "not_implemented";
  supported_connector_kind: "readiness_stub";
  notes: string[];
}

// Channel Gateway primitives
export interface ChannelProvider {
  id: UUID;
  provider_key: string;
  provider_display_name: string;
  provider_kind: string;
  provider_status: string;
  is_real_provider: boolean;
  supports_multi_bot: boolean;
  supports_inbound: boolean;
  supports_outbound: boolean;
  supports_low_frequency_checkin: boolean;
  requires_external_token: boolean;
  config_schema_json?: JsonObject;
}

export interface ChannelBotRegistry {
  id: UUID;
  provider_id: UUID;
  user_id?: UUID | null;
  bot_key: string;
  bot_display_name: string;
  bot_status: string;
  token_status: string;
  stores_plaintext_token: boolean;
  external_application_id_hash?: string | null;
  external_bot_user_id_hash?: string | null;
  safe_metadata_json?: JsonObject;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface ChannelBinding {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  provider_id: UUID;
  provider_bot_id?: UUID | null;
  presence_channel_binding_id?: UUID | null;
  binding_status: string;
  binding_scope: string;
  permission_scope: string;
  outbound_policy: string;
  memory_policy: string;
  requires_user_approval: boolean;
  can_receive_inbound: boolean;
  can_send_outbound: boolean;
  checkin_enabled: boolean;
  memory_write_requires_review: boolean;
  raw_message_storage_allowed: boolean;
  stores_plaintext_token: boolean;
  external_channel_ref_hash?: string | null;
  external_guild_ref_hash?: string | null;
  provider?: ChannelProvider | null;
  provider_bot?: ChannelBotRegistry | null;
  recent_trace_events?: ChannelTraceEvent[];
  recent_audit_logs?: ChannelAuditLog[];
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface DiscordBotIdentityStatus {
  bot_key: string;
  bot_display_name: string;
  enabled: boolean;
  status?: string;
  token_status: string;
  token_secret_ref_configured: boolean;
  connection_status?: string;
  bot_user_id?: string | null;
  application_id?: string | null;
  app_id?: string | null;
  public_key?: string | null;
  oauth2_url?: string | null;
  guild_id?: string | null;
  default_channel_id?: string | null;
  memory_review_channel_id?: string | null;
  audit_log_channel_id?: string | null;
  companion_id?: UUID | null;
  provider_bot_id?: UUID | null;
}

export interface DiscordDmBinding {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  companion_name?: string | null;
  provider_bot_id: UUID;
  bot_key?: string | null;
  bot_display_name?: string | null;
  companion_channel_identity_id: UUID;
  channel_binding_id: UUID;
  conversation_id: UUID;
  conversation_title?: string | null;
  external_user_ref_hash_prefix: string;
  external_channel_ref_hash_prefix: string;
  binding_status: "active" | "paused" | "revoked";
  binding_source: "first_dm" | "web" | "slash_command";
  revision: number;
  last_inbound_at?: Timestamp | null;
  last_outbound_at?: Timestamp | null;
  revoked_at?: Timestamp | null;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
  provider_channel_ref_exposed: false;
}

export interface DiscordDmDelivery {
  id: UUID;
  dm_binding_id: UUID;
  conversation_id: UUID;
  assistant_message_id: UUID;
  trace_run_id?: UUID | null;
  delivery_status: "queued" | "leased" | "retry_scheduled" | "delivered" | "failed" | "cancelled" | "suppressed";
  attempt_count: number;
  max_attempts: number;
  next_attempt_at?: Timestamp | null;
  last_error_code?: string | null;
  last_error_summary?: string | null;
  delivered_at?: Timestamp | null;
  cancelled_at?: Timestamp | null;
  created_at?: Timestamp | null;
  updated_at?: Timestamp | null;
}

export interface ChannelMessageEvent {
  id: UUID;
  user_id: UUID;
  channel_binding_id?: UUID | null;
  provider_id?: UUID | null;
  provider_bot_id?: UUID | null;
  companion_id?: UUID | null;
  message_direction: string;
  message_status: string;
  message_summary: string;
  requires_user_review: boolean;
  payload_is_ephemeral: boolean;
  raw_payload_storage_allowed: boolean;
  safe_payload_json?: JsonObject;
  occurred_at?: Timestamp | null;
}

export interface ChannelDeliveryEvent {
  id: UUID;
  user_id: UUID;
  channel_binding_id: UUID;
  channel_message_event_id?: UUID | null;
  provider_id: UUID;
  provider_bot_id?: UUID | null;
  delivery_status: string;
  delivery_mode: string;
  delivery_summary: string;
  raw_payload_storage_allowed: boolean;
  safe_delivery_payload_json?: JsonObject;
  queued_at?: Timestamp | null;
  delivered_at?: Timestamp | null;
}

export interface ChannelMemoryCandidate {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  channel_binding_id: UUID;
  provider_id: UUID;
  provider_bot_id?: UUID | null;
  channel_message_event_id?: UUID | null;
  candidate_status: string;
  target_memory_scope: string;
  candidate_summary: string;
  suggested_memory_content?: string;
  salience_score: number;
  requires_user_review: boolean;
  auto_commit_allowed: boolean;
  raw_payload_storage_allowed: boolean;
  safe_evidence_json?: JsonObject;
}

export interface ChannelMemoryReview {
  id: UUID;
  user_id: UUID;
  channel_memory_candidate_id: UUID;
  review_decision: string;
  memory_write_allowed_after_review: boolean;
  safe_review_payload_json?: JsonObject;
  reviewed_at?: Timestamp | null;
}

export interface ChannelPresencePolicy {
  id: UUID;
  user_id: UUID;
  companion_id: UUID;
  channel_binding_id: UUID;
  provider_id: UUID;
  provider_bot_id?: UUID | null;
  policy_status: string;
  presence_mode: string;
  reply_only_default: boolean;
  low_frequency_checkin_enabled: boolean;
  channel_mute: boolean;
  outbound_disabled: boolean;
  daily_presence_budget: number;
  remaining_presence_budget: number;
  quiet_hours_enforced: boolean;
  focus_mode_enforced: boolean;
  meaningful_silence_enforced: boolean;
  checkin_setting?: JsonObject | null;
}

export interface ChannelContinuityHandoff {
  id: UUID;
  user_id: UUID;
  companion_id?: UUID | null;
  channel_binding_id?: UUID | null;
  provider_id?: UUID | null;
  provider_bot_id?: UUID | null;
  trace_event_type: string;
  trace_status: string;
  handoff_status?: string | null;
  direction?: string | null;
  visibility_decision?: string | null;
  visibility_reason?: string | null;
  raw_history_included: boolean;
  private_memory_included: boolean;
  safe_trace_payload_json?: JsonObject;
  occurred_at?: Timestamp | null;
}

export interface ChannelTraceEvent {
  id: UUID;
  user_id: UUID;
  companion_id?: UUID | null;
  channel_binding_id?: UUID | null;
  provider_id?: UUID | null;
  provider_bot_id?: UUID | null;
  trace_event_type: string;
  trace_status: string;
  trace_summary: string;
  safe_trace_payload_json?: JsonObject;
  occurred_at?: Timestamp | null;
}

export interface ChannelAuditLog {
  id: UUID;
  user_id: UUID;
  channel_binding_id?: UUID | null;
  provider_id?: UUID | null;
  provider_bot_id?: UUID | null;
  channel_trace_event_id?: UUID | null;
  audit_log_type: string;
  audit_summary: string;
  safe_audit_payload_json?: JsonObject;
  occurred_at?: Timestamp | null;
}

export interface ChannelRevokeEvent {
  id: UUID;
  user_id: UUID;
  channel_binding_id?: UUID | null;
  provider_id?: UUID | null;
  provider_bot_id?: UUID | null;
  trace_run_id?: UUID | null;
  revoke_status: string;
  revoke_scope: string;
  stops_inbound: boolean;
  stops_outbound: boolean;
  stops_checkins: boolean;
  clears_ephemeral_buffer: boolean;
  disables_memory_candidates: boolean;
  audit_required: boolean;
  revoke_reason?: string | null;
  applied_at?: Timestamp | null;
}
