"""phase3_01_tool_file_project

Revision ID: p3_01_tool_file_project
Revises: p2_05_relationship
Create Date: 2026-05-31 00:00:00.000000

Create Phase 3 Tool, File Context, and Project Task schema.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "p3_01_tool_file"
down_revision: Union[str, Sequence[str], None] = "p2_05_relationship"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tool_definitions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id),
            companion_id UUID REFERENCES companions(id),
            name TEXT NOT NULL,
            display_name TEXT,
            description TEXT,
            tool_type TEXT NOT NULL,
            risk_level TEXT NOT NULL DEFAULT 'medium',
            permission_policy TEXT NOT NULL DEFAULT 'ask_every_time',
            is_enabled BOOLEAN NOT NULL DEFAULT true,
            input_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT tool_definitions_type_check
                CHECK (tool_type IN ('internal', 'local_command', 'http_api', 'mock', 'manual')),
            CONSTRAINT tool_definitions_risk_level_check
                CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
            CONSTRAINT tool_definitions_permission_policy_check
                CHECK (permission_policy IN ('not_required', 'ask_once', 'ask_every_time', 'disabled'))
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX idx_tool_definitions_name ON tool_definitions(name) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX idx_tool_definitions_companion_enabled ON tool_definitions(companion_id, is_enabled)")

    op.execute(
        """
        CREATE TABLE tool_permissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            tool_definition_id UUID NOT NULL REFERENCES tool_definitions(id),
            policy TEXT NOT NULL DEFAULT 'ask_every_time',
            status TEXT NOT NULL DEFAULT 'active',
            allowed_until TIMESTAMPTZ,
            reason TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT tool_permissions_policy_check
                CHECK (policy IN ('not_required', 'ask_once', 'ask_every_time', 'disabled')),
            CONSTRAINT tool_permissions_status_check
                CHECK (status IN ('active', 'denied', 'revoked', 'expired'))
        )
        """
    )
    op.execute("CREATE INDEX idx_tool_permissions_user_tool ON tool_permissions(user_id, tool_definition_id)")
    op.execute("CREATE INDEX idx_tool_permissions_companion_status ON tool_permissions(companion_id, status)")

    op.execute(
        """
        CREATE TABLE tool_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            conversation_id UUID REFERENCES conversations(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            trace_step_id UUID REFERENCES trace_steps(id),
            tool_definition_id UUID REFERENCES tool_definitions(id),
            requested_by TEXT NOT NULL DEFAULT 'agent',
            status TEXT NOT NULL DEFAULT 'planned',
            risk_level TEXT NOT NULL DEFAULT 'medium',
            permission_required BOOLEAN NOT NULL DEFAULT true,
            permission_granted BOOLEAN NOT NULL DEFAULT false,
            input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            elapsed_ms INTEGER,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT tool_runs_status_check
                CHECK (status IN ('planned', 'permission_required', 'running', 'succeeded', 'failed', 'cancelled', 'blocked')),
            CONSTRAINT tool_runs_risk_level_check
                CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
            CONSTRAINT tool_runs_elapsed_ms_check
                CHECK (elapsed_ms IS NULL OR elapsed_ms >= 0)
        )
        """
    )
    op.execute("CREATE INDEX idx_tool_runs_companion_created ON tool_runs(companion_id, created_at DESC)")
    op.execute("CREATE INDEX idx_tool_runs_trace ON tool_runs(trace_run_id)")
    op.execute("CREATE INDEX idx_tool_runs_status ON tool_runs(status, created_at DESC)")

    op.execute(
        """
        CREATE TABLE tool_run_steps (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tool_run_id UUID NOT NULL REFERENCES tool_runs(id) ON DELETE CASCADE,
            step_order INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_message TEXT,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            elapsed_ms INTEGER,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT tool_run_steps_status_check
                CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'cancelled')),
            CONSTRAINT tool_run_steps_elapsed_ms_check
                CHECK (elapsed_ms IS NULL OR elapsed_ms >= 0)
        )
        """
    )
    op.execute("CREATE INDEX idx_tool_run_steps_run_order ON tool_run_steps(tool_run_id, step_order)")

    op.execute(
        """
        CREATE TABLE tool_run_artifacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tool_run_id UUID NOT NULL REFERENCES tool_runs(id) ON DELETE CASCADE,
            artifact_type TEXT NOT NULL,
            title TEXT,
            uri TEXT,
            content_text TEXT,
            content_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX idx_tool_run_artifacts_run ON tool_run_artifacts(tool_run_id)")

    op.execute(
        """
        CREATE TABLE file_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            source_type TEXT NOT NULL,
            name TEXT NOT NULL,
            uri TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT file_sources_type_check
                CHECK (source_type IN ('upload', 'local_path', 'url', 'manual_note', 'tool_artifact')),
            CONSTRAINT file_sources_status_check
                CHECK (status IN ('active', 'archived', 'deleted', 'disabled'))
        )
        """
    )
    op.execute("CREATE INDEX idx_file_sources_companion_created ON file_sources(companion_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE file_documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            file_source_id UUID REFERENCES file_sources(id),
            title TEXT NOT NULL,
            document_type TEXT NOT NULL DEFAULT 'unknown',
            status TEXT NOT NULL DEFAULT 'created',
            mime_type TEXT,
            uri TEXT,
            content_hash TEXT,
            summary TEXT,
            processing_error TEXT,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT file_documents_status_check
                CHECK (status IN ('created', 'processing', 'ready', 'failed', 'archived', 'deleted')),
            CONSTRAINT file_documents_chunk_count_check
                CHECK (chunk_count >= 0)
        )
        """
    )
    op.execute("CREATE INDEX idx_file_documents_companion_status ON file_documents(companion_id, status, created_at DESC)")
    op.execute("CREATE INDEX idx_file_documents_source ON file_documents(file_source_id)")

    op.execute(
        """
        CREATE TABLE file_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            file_document_id UUID NOT NULL REFERENCES file_documents(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            chunk_index INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ready',
            content TEXT NOT NULL,
            summary TEXT,
            token_count INTEGER,
            embedding vector(768),
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT file_chunks_status_check
                CHECK (status IN ('ready', 'suppressed', 'outdated', 'deleted')),
            CONSTRAINT file_chunks_chunk_index_check
                CHECK (chunk_index >= 0),
            CONSTRAINT file_chunks_token_count_check
                CHECK (token_count IS NULL OR token_count >= 0)
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX idx_file_chunks_document_index ON file_chunks(file_document_id, chunk_index) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX idx_file_chunks_companion_created ON file_chunks(companion_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE file_context_usages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            conversation_id UUID REFERENCES conversations(id),
            message_id UUID REFERENCES messages(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            trace_step_id UUID REFERENCES trace_steps(id),
            file_document_id UUID REFERENCES file_documents(id),
            file_chunk_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
            usage_purpose TEXT NOT NULL DEFAULT 'response_generation',
            selected_for_context BOOLEAN NOT NULL DEFAULT false,
            used_in_response BOOLEAN NOT NULL DEFAULT false,
            evidence_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            citation_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT file_context_usages_evidence_score_check
                CHECK (evidence_score BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_file_context_usages_trace ON file_context_usages(trace_run_id)")
    op.execute("CREATE INDEX idx_file_context_usages_document ON file_context_usages(file_document_id)")

    op.execute(
        """
        CREATE TABLE project_milestones (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            target_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            priority DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT project_milestones_status_check
                CHECK (status IN ('planned', 'active', 'completed', 'blocked', 'cancelled', 'archived')),
            CONSTRAINT project_milestones_priority_check
                CHECK (priority BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_project_milestones_companion_status ON project_milestones(companion_id, status, created_at DESC)")

    op.execute(
        """
        CREATE TABLE project_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            milestone_id UUID REFERENCES project_milestones(id),
            conversation_id UUID REFERENCES conversations(id),
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'todo',
            priority DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            due_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            evidence_summary TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT project_tasks_status_check
                CHECK (status IN ('todo', 'in_progress', 'blocked', 'done', 'cancelled', 'archived')),
            CONSTRAINT project_tasks_priority_check
                CHECK (priority BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_project_tasks_companion_status ON project_tasks(companion_id, status, created_at DESC)")
    op.execute("CREATE INDEX idx_project_tasks_milestone ON project_tasks(milestone_id)")

    op.execute(
        """
        CREATE TABLE project_task_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_task_id UUID NOT NULL REFERENCES project_tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            event_type TEXT NOT NULL,
            previous_status TEXT,
            new_status TEXT,
            description TEXT,
            event_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_project_task_events_task_created ON project_task_events(project_task_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE project_task_evidence_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_task_id UUID NOT NULL REFERENCES project_tasks(id) ON DELETE CASCADE,
            evidence_type TEXT NOT NULL,
            evidence_id UUID NOT NULL,
            relevance_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            note TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT project_task_evidence_type_check
                CHECK (evidence_type IN ('memory', 'file_document', 'file_chunk', 'message', 'trace_run', 'trace_step', 'tool_run', 'bad_case', 'regression_case', 'evaluation_result')),
            CONSTRAINT project_task_evidence_relevance_check
                CHECK (relevance_score BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_project_task_evidence_links_task ON project_task_evidence_links(project_task_id)")
    op.execute("CREATE INDEX idx_project_task_evidence_links_evidence ON project_task_evidence_links(evidence_type, evidence_id)")


def downgrade() -> None:
    for table in [
        "project_task_evidence_links",
        "project_task_events",
        "project_tasks",
        "project_milestones",
        "file_context_usages",
        "file_chunks",
        "file_documents",
        "file_sources",
        "tool_run_artifacts",
        "tool_run_steps",
        "tool_runs",
        "tool_permissions",
        "tool_definitions",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
