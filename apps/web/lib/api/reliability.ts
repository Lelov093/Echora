import { api } from "./client";

export type ReliabilityDomain = {
  key: string;
  label: string;
  status: "healthy" | "attention" | "blocked" | "available" | "unavailable";
  total: number;
  active?: number;
  terminal?: number;
  failed?: number;
  stuck?: number;
  status_counts: Record<string, number>;
  safe_reason?: string;
};

export type ReliabilityDiagnostics = {
  contract_version: string;
  companion_id: string;
  companion_status: string;
  generated_at: string;
  overall_status: "healthy" | "attention" | "blocked";
  runtime_domains: ReliabilityDomain[];
  state_domains: ReliabilityDomain[];
  validation_matrix: Array<{
    key: string;
    label: string;
    scope: "companion";
    all_time_evidence_count: number;
    last_30d_evidence_count: number;
    evidence_sources: string[];
    coverage_status: "evidence_available" | "no_evidence";
    quality_conclusion: "snapshot_only_no_long_term_claim";
  }>;
  quality: { open_bad_cases: number; failed_regression_results: number };
  safety: {
    active_hard_stops: number;
    revoked_channel_bindings: number;
    pending_shared_reviews: number;
    memory_reranker_policy_mode: string;
    presence_bandit_policy_mode: string;
    observer_auto_speaker: boolean;
  };
  capabilities: Record<string, boolean | string>;
  retention_boundaries: Record<string, string>;
  content_disclosure: string;
};

export type DataRightsOperation = "export" | "forget_memory" | "archive_companion" | "disconnect_channels" | "revoke_channels" | "permanent_delete";

export type DataRightsDryRun = {
  contract_version: string;
  companion_id: string;
  operation: DataRightsOperation;
  dry_run: true;
  executed: false;
  supported_write_path: boolean;
  irreversible: boolean;
  separate_authorization_required: boolean;
  ready_for_explicit_execution: boolean;
  blockers: string[];
  effect_summary: string;
  affected_counts: Record<string, number>;
  retained_evidence: string[];
  review_gates: string[];
  content_disclosure: "counts_only";
};

export type CompanionDeletionRequest = {
  contract_version: string;
  id: string;
  companion_id: string | null;
  companion_display_name: string | null;
  status: "trash" | "purging" | "completed" | "restored" | "failed";
  deletion_mode: "recovery_window" | "immediate";
  current_stage: string;
  requested_at: string;
  purge_after: string;
  completed_at: string | null;
  restored_at: string | null;
  backup_delete_due_at: string | null;
  affected_counts: Record<string, number>;
  deleted_counts: Record<string, number>;
  failure_code: string | null;
  failure_stage: string | null;
  can_restore: boolean;
  can_retry: boolean;
  content_disclosure: "counts_and_safe_status_only";
};

export type CompanionDataExport = {
  contract_version: "companion-data-export.v1";
  exported_at: string;
  owner_id: string;
  companion: {
    id: string;
    name: string;
    [key: string]: unknown;
  };
  sections: Record<string, Array<Record<string, unknown>>>;
  manifest: {
    format: "json";
    section_counts: Record<string, number>;
    excluded: string[];
    sha256: string;
  };
};

export const getReliabilityDiagnostics = (companionId: string) =>
  api.get<ReliabilityDiagnostics>(`/companions/${companionId}/reliability-diagnostics`);

export const dryRunDataRights = (companionId: string, operation: DataRightsOperation, targetId?: string) =>
  api.post<DataRightsDryRun>(`/companions/${companionId}/data-rights/dry-run`, { operation, target_id: targetId || undefined });

export const exportCompanionData = (companionId: string) =>
  api.post<CompanionDataExport>(
    `/companions/${companionId}/data-rights/export`,
  );

export const getCompanionDeletionRequest = (companionId: string) =>
  api.get<CompanionDeletionRequest | null>(`/companions/${companionId}/data-rights/deletion-request`);

export const getDeletionRequest = (requestId: string) =>
  api.get<CompanionDeletionRequest>(`/data-rights/deletion-requests/${requestId}`);

export const createCompanionDeletionRequest = (
  companionId: string,
  input: {
    confirmation_name: string;
    skip_recovery_window: boolean;
    export_choice: "skip" | "completed";
    idempotency_key: string;
  },
) =>
  api.post<CompanionDeletionRequest>(
    `/companions/${companionId}/data-rights/deletion-requests`,
    input,
  );

export const restoreCompanionDeletionRequest = (requestId: string) =>
  api.post<CompanionDeletionRequest>(
    `/data-rights/deletion-requests/${requestId}/restore`,
  );

export const executeCompanionDeletionRequest = (requestId: string) =>
  api.post<CompanionDeletionRequest>(
    `/data-rights/deletion-requests/${requestId}/execute`,
    { allow_before_due: true },
  );
