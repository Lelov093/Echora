"""phase3_02_replay_badcase

Revision ID: p3_02_replay_badcase
Revises: p3_01_tool_file_project
Create Date: 2026-05-31 00:00:00.000000

Create Phase 3 Replay and Bad Case Inbox schema.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "p3_02_replay_badcase"
down_revision: Union[str, Sequence[str], None] = "p3_01_tool_file"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE agent_run_replays (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            conversation_id UUID REFERENCES conversations(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            replay_type TEXT NOT NULL DEFAULT 'static',
            status TEXT NOT NULL DEFAULT 'created',
            title TEXT,
            input_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            memory_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            file_context_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            tool_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            trace_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            summary TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT agent_run_replays_type_check
                CHECK (replay_type IN ('static', 'trace_replay', 'regression_seed')),
            CONSTRAINT agent_run_replays_status_check
                CHECK (status IN ('created', 'ready', 'failed', 'archived', 'deleted'))
        )
        """
    )
    op.execute("CREATE INDEX idx_agent_run_replays_companion_created ON agent_run_replays(companion_id, created_at DESC)")
    op.execute("CREATE INDEX idx_agent_run_replays_trace ON agent_run_replays(trace_run_id)")

    op.execute(
        """
        CREATE TABLE trace_replay_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            trace_run_id UUID NOT NULL REFERENCES trace_runs(id),
            agent_run_replay_id UUID REFERENCES agent_run_replays(id),
            status TEXT NOT NULL DEFAULT 'created',
            replay_mode TEXT NOT NULL DEFAULT 'summary_only',
            result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT trace_replay_sessions_status_check
                CHECK (status IN ('created', 'running', 'completed', 'failed', 'cancelled')),
            CONSTRAINT trace_replay_sessions_mode_check
                CHECK (replay_mode IN ('summary_only', 'key_events', 'full_static', 'reexecute_mock'))
        )
        """
    )
    op.execute("CREATE INDEX idx_trace_replay_sessions_trace_created ON trace_replay_sessions(trace_run_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE replay_annotations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_run_replay_id UUID NOT NULL REFERENCES agent_run_replays(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            annotation_type TEXT NOT NULL DEFAULT 'note',
            target_ref_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            content TEXT NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX idx_replay_annotations_replay_created ON replay_annotations(agent_run_replay_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE bad_case_inbox_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            conversation_id UUID REFERENCES conversations(id),
            message_id UUID REFERENCES messages(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            replay_id UUID REFERENCES agent_run_replays(id),
            source_type TEXT NOT NULL,
            case_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'open',
            evidence_summary TEXT,
            suggested_fix TEXT,
            created_regression_case_id UUID,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT bad_case_inbox_source_type_check
                CHECK (source_type IN ('manual', 'trace', 'replay', 'tool_run', 'file_context', 'evaluation_result', 'regression_result', 'feedback_event', 'conversation_run')),
            CONSTRAINT bad_case_inbox_case_type_check
                CHECK (case_type IN ('wrong_memory_used', 'important_memory_missing', 'memory_pollution', 'outdated_memory_used', 'wrong_tone', 'wrong_presence', 'tool_permission_error', 'tool_result_misread', 'file_context_misread', 'evidence_insufficient', 'evaluation_failed', 'regression_failed', 'provider_fallback_error', 'growth_inconsistency', 'boundary_violation', 'other')),
            CONSTRAINT bad_case_inbox_severity_check
                CHECK (severity IN ('low', 'medium', 'high', 'critical')),
            CONSTRAINT bad_case_inbox_status_check
                CHECK (status IN ('open', 'triaged', 'in_progress', 'resolved', 'dismissed', 'converted_to_regression'))
        )
        """
    )
    op.execute("CREATE INDEX idx_bad_case_inbox_companion_status ON bad_case_inbox_items(companion_id, status, created_at DESC)")
    op.execute("CREATE INDEX idx_bad_case_inbox_trace ON bad_case_inbox_items(trace_run_id)")
    op.execute("CREATE INDEX idx_bad_case_inbox_type_severity ON bad_case_inbox_items(case_type, severity)")

    op.execute(
        """
        CREATE TABLE bad_case_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bad_case_inbox_item_id UUID NOT NULL REFERENCES bad_case_inbox_items(id) ON DELETE CASCADE,
            link_type TEXT NOT NULL,
            linked_id UUID NOT NULL,
            relation TEXT NOT NULL DEFAULT 'evidence',
            note TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT bad_case_links_type_check
                CHECK (link_type IN ('memory', 'memory_candidate', 'message', 'trace_run', 'trace_step', 'tool_run', 'file_document', 'file_chunk', 'feedback_event', 'evaluation_result', 'regression_result', 'growth_candidate', 'presence_opportunity', 'llm_call_record', 'replay'))
        )
        """
    )
    op.execute("CREATE INDEX idx_bad_case_links_item ON bad_case_links(bad_case_inbox_item_id)")
    op.execute("CREATE INDEX idx_bad_case_links_target ON bad_case_links(link_type, linked_id)")

    op.execute(
        """
        CREATE TABLE bad_case_triage_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bad_case_inbox_item_id UUID NOT NULL REFERENCES bad_case_inbox_items(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            previous_status TEXT,
            new_status TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT bad_case_triage_status_check
                CHECK (new_status IN ('open', 'triaged', 'in_progress', 'resolved', 'dismissed', 'converted_to_regression'))
        )
        """
    )
    op.execute("CREATE INDEX idx_bad_case_triage_events_item_created ON bad_case_triage_events(bad_case_inbox_item_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE bad_case_clusters (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            title TEXT NOT NULL,
            description TEXT,
            case_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            item_count INTEGER NOT NULL DEFAULT 0,
            representative_item_id UUID REFERENCES bad_case_inbox_items(id),
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT bad_case_clusters_status_check
                CHECK (status IN ('open', 'triaged', 'resolved', 'dismissed')),
            CONSTRAINT bad_case_clusters_item_count_check
                CHECK (item_count >= 0)
        )
        """
    )
    op.execute("CREATE INDEX idx_bad_case_clusters_companion_status ON bad_case_clusters(companion_id, status, created_at DESC)")


def downgrade() -> None:
    for table in [
        "bad_case_clusters",
        "bad_case_triage_events",
        "bad_case_links",
        "bad_case_inbox_items",
        "replay_annotations",
        "trace_replay_sessions",
        "agent_run_replays",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
