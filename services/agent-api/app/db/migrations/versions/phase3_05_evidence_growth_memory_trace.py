"""phase3_05_evidence_growth_memory_trace

Revision ID: p3_05_evidence_growth_memory_trace
Revises: p3_04_provider_strategy
Create Date: 2026-05-31 00:00:00.000000

Create Phase 3 Evidence, Growth Consistency, Outdated Memory schema and
enhance existing Phase 1/2 tables for Trace V3.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "p3_05_evidence_trace"
down_revision: Union[str, Sequence[str], None] = "p3_04_provider_strategy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE evidence_sufficiency_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            conversation_id UUID REFERENCES conversations(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            trace_step_id UUID REFERENCES trace_steps(id),
            target_type TEXT NOT NULL,
            target_id UUID,
            sufficiency_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'needs_more_evidence',
            missing_evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            explanation TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT evidence_sufficiency_events_target_type_check
                CHECK (target_type IN ('assistant_response', 'memory_candidate', 'growth_candidate', 'tool_result', 'file_answer', 'evaluation_result', 'project_task_suggestion', 'presence_opportunity')),
            CONSTRAINT evidence_sufficiency_events_status_check
                CHECK (status IN ('sufficient', 'needs_more_evidence', 'conflicting', 'unverified', 'not_applicable')),
            CONSTRAINT evidence_sufficiency_events_score_check
                CHECK (sufficiency_score BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_evidence_sufficiency_events_trace ON evidence_sufficiency_events(trace_run_id)")
    op.execute("CREATE INDEX idx_evidence_sufficiency_events_target ON evidence_sufficiency_events(target_type, target_id)")

    op.execute(
        """
        CREATE TABLE growth_consistency_checks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            growth_candidate_id UUID REFERENCES growth_candidates(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            consistency_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            risk_level TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'needs_review',
            conflict_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            duplication_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            profile_patch_preview_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            recommendation TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT growth_consistency_checks_score_check
                CHECK (consistency_score BETWEEN 0 AND 1),
            CONSTRAINT growth_consistency_checks_risk_level_check
                CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
            CONSTRAINT growth_consistency_checks_status_check
                CHECK (status IN ('passed', 'warning', 'blocked', 'needs_review'))
        )
        """
    )
    op.execute("CREATE INDEX idx_growth_consistency_checks_candidate ON growth_consistency_checks(growth_candidate_id)")
    op.execute("CREATE INDEX idx_growth_consistency_checks_trace ON growth_consistency_checks(trace_run_id)")

    op.execute(
        """
        CREATE TABLE outdated_memory_flags (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            memory_id UUID NOT NULL REFERENCES memories(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            reason TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            status TEXT NOT NULL DEFAULT 'open',
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            suggested_action TEXT NOT NULL DEFAULT 'review',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT outdated_memory_flags_confidence_check
                CHECK (confidence BETWEEN 0 AND 1),
            CONSTRAINT outdated_memory_flags_status_check
                CHECK (status IN ('open', 'reviewed', 'dismissed', 'resolved')),
            CONSTRAINT outdated_memory_flags_suggested_action_check
                CHECK (suggested_action IN ('review', 'keep', 'edit', 'fade', 'suppress', 'archive', 'delete', 'reject_flag'))
        )
        """
    )
    op.execute("CREATE INDEX idx_outdated_memory_flags_memory_status ON outdated_memory_flags(memory_id, status)")
    op.execute("CREATE INDEX idx_outdated_memory_flags_companion_created ON outdated_memory_flags(companion_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE outdated_memory_reviews (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            outdated_memory_flag_id UUID NOT NULL REFERENCES outdated_memory_flags(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            memory_id UUID NOT NULL REFERENCES memories(id),
            decision TEXT NOT NULL,
            edited_content TEXT,
            feedback_event_id UUID REFERENCES feedback_events(id),
            lifecycle_event_id UUID REFERENCES memory_lifecycle_events(id),
            reason TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT outdated_memory_reviews_decision_check
                CHECK (decision IN ('keep', 'edit', 'fade', 'suppress', 'archive', 'delete', 'reject_flag'))
        )
        """
    )
    op.execute("CREATE INDEX idx_outdated_memory_reviews_flag ON outdated_memory_reviews(outdated_memory_flag_id)")

    op.execute("ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS tool_run_ids UUID[] NOT NULL DEFAULT '{}'::uuid[]")
    op.execute("ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS file_context_usage_ids UUID[] NOT NULL DEFAULT '{}'::uuid[]")
    op.execute("ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS evidence_sufficiency_event_ids UUID[] NOT NULL DEFAULT '{}'::uuid[]")
    op.execute("ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS memory_reranker_run_ids UUID[] NOT NULL DEFAULT '{}'::uuid[]")
    op.execute("ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS presence_policy_run_ids UUID[] NOT NULL DEFAULT '{}'::uuid[]")
    op.execute("ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS bad_case_signal_ids UUID[] NOT NULL DEFAULT '{}'::uuid[]")
    op.execute("ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS evaluation_signal_ids UUID[] NOT NULL DEFAULT '{}'::uuid[]")
    op.execute("ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS llm_call_record_ids UUID[] NOT NULL DEFAULT '{}'::uuid[]")
    op.execute("ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS trace_v3_summary JSONB NOT NULL DEFAULT '{}'::jsonb")

    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS tool_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS file_context_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS reranker_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS presence_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS bad_case_signal_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS evaluation_signal_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS provider_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS outdated_memory_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE trace_steps ADD COLUMN IF NOT EXISTS growth_consistency_json JSONB NOT NULL DEFAULT '{}'::jsonb")

    op.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS outdated_flag_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS last_outdated_flag_at TIMESTAMPTZ")
    op.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS phase3_reranker_score DOUBLE PRECISION")
    op.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS file_evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'memories_outdated_flag_count_check'
            ) THEN
                ALTER TABLE memories
                ADD CONSTRAINT memories_outdated_flag_count_check
                CHECK (outdated_flag_count >= 0);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'memories_phase3_reranker_score_check'
            ) THEN
                ALTER TABLE memories
                ADD CONSTRAINT memories_phase3_reranker_score_check
                CHECK (phase3_reranker_score IS NULL OR phase3_reranker_score BETWEEN 0 AND 1);
            END IF;
        END $$;
        """
    )

    op.execute("ALTER TABLE presence_opportunities ADD COLUMN IF NOT EXISTS presence_policy_run_id UUID REFERENCES presence_policy_runs(id)")
    op.execute("ALTER TABLE presence_opportunities ADD COLUMN IF NOT EXISTS phase3_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE presence_opportunities ADD COLUMN IF NOT EXISTS phase3_selected_action TEXT")

    op.execute("ALTER TABLE growth_candidates ADD COLUMN IF NOT EXISTS growth_consistency_check_id UUID REFERENCES growth_consistency_checks(id)")
    op.execute("ALTER TABLE growth_candidates ADD COLUMN IF NOT EXISTS evidence_sufficiency_event_id UUID REFERENCES evidence_sufficiency_events(id)")
    op.execute("ALTER TABLE growth_candidates ADD COLUMN IF NOT EXISTS phase3_consistency_json JSONB NOT NULL DEFAULT '{}'::jsonb")

    op.execute("ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS tool_run_id UUID REFERENCES tool_runs(id)")
    op.execute("ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS file_context_usage_id UUID REFERENCES file_context_usages(id)")
    op.execute("ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS evaluation_result_id UUID REFERENCES evaluation_results(id)")
    op.execute("ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS regression_result_id UUID REFERENCES regression_results(id)")
    op.execute("ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS strategy_learning_json JSONB NOT NULL DEFAULT '{}'::jsonb")

    op.execute("ALTER TABLE bad_cases ADD COLUMN IF NOT EXISTS bad_case_inbox_item_id UUID REFERENCES bad_case_inbox_items(id)")
    op.execute("ALTER TABLE bad_cases ADD COLUMN IF NOT EXISTS phase3_evidence_links JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE bad_cases ADD COLUMN IF NOT EXISTS replay_id UUID REFERENCES agent_run_replays(id)")
    op.execute("ALTER TABLE bad_cases ADD COLUMN IF NOT EXISTS evaluation_result_id UUID REFERENCES evaluation_results(id)")
    op.execute("ALTER TABLE bad_cases ADD COLUMN IF NOT EXISTS regression_result_id UUID REFERENCES regression_results(id)")


def downgrade() -> None:
    for table in [
        "outdated_memory_reviews",
        "outdated_memory_flags",
        "growth_consistency_checks",
        "evidence_sufficiency_events",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    drops = {
        "bad_cases": ["regression_result_id", "evaluation_result_id", "replay_id", "phase3_evidence_links", "bad_case_inbox_item_id"],
        "feedback_events": ["strategy_learning_json", "regression_result_id", "evaluation_result_id", "file_context_usage_id", "tool_run_id"],
        "growth_candidates": ["phase3_consistency_json", "evidence_sufficiency_event_id", "growth_consistency_check_id"],
        "presence_opportunities": ["phase3_selected_action", "phase3_policy_json", "presence_policy_run_id"],
        "memories": ["file_evidence_refs", "phase3_reranker_score", "last_outdated_flag_at", "outdated_flag_count"],
        "trace_steps": ["growth_consistency_json", "outdated_memory_json", "provider_json", "evaluation_signal_json", "bad_case_signal_json", "presence_policy_json", "reranker_json", "evidence_json", "file_context_json", "tool_json"],
        "trace_runs": ["trace_v3_summary", "llm_call_record_ids", "evaluation_signal_ids", "bad_case_signal_ids", "presence_policy_run_ids", "memory_reranker_run_ids", "evidence_sufficiency_event_ids", "file_context_usage_ids", "tool_run_ids"],
    }
    for table, columns in drops.items():
        for column in columns:
            op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column} CASCADE")
