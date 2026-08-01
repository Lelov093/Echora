"""phase3_03_evaluation_regression

Revision ID: p3_03_evaluation_regression
Revises: p3_02_replay_badcase
Create Date: 2026-05-31 00:00:00.000000

Create Phase 3 Evaluation and Regression schema.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "p3_03_eval_regression"
down_revision: Union[str, Sequence[str], None] = "p3_02_replay_badcase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE evaluation_datasets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            name TEXT NOT NULL,
            description TEXT,
            dataset_type TEXT NOT NULL DEFAULT 'manual',
            status TEXT NOT NULL DEFAULT 'active',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT evaluation_datasets_status_check
                CHECK (status IN ('active', 'archived', 'deleted', 'disabled'))
        )
        """
    )
    op.execute("CREATE INDEX idx_evaluation_datasets_companion_status ON evaluation_datasets(companion_id, status, created_at DESC)")

    op.execute(
        """
        CREATE TABLE evaluation_cases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            dataset_id UUID REFERENCES evaluation_datasets(id) ON DELETE SET NULL,
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            case_type TEXT NOT NULL,
            title TEXT NOT NULL,
            input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            expected_behavior TEXT,
            expected_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            status TEXT NOT NULL DEFAULT 'active',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT evaluation_cases_type_check
                CHECK (case_type IN ('memory_retrieval', 'memory_write', 'presence', 'tool_use', 'file_context', 'evidence_sufficiency', 'growth_consistency', 'mode_router', 'conversation_quality', 'regression_seed')),
            CONSTRAINT evaluation_cases_status_check
                CHECK (status IN ('active', 'disabled', 'archived', 'deleted'))
        )
        """
    )
    op.execute("CREATE INDEX idx_evaluation_cases_dataset ON evaluation_cases(dataset_id)")
    op.execute("CREATE INDEX idx_evaluation_cases_companion_type ON evaluation_cases(companion_id, case_type)")

    op.execute(
        """
        CREATE TABLE evaluation_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            dataset_id UUID REFERENCES evaluation_datasets(id),
            status TEXT NOT NULL DEFAULT 'pending',
            judge_type TEXT NOT NULL DEFAULT 'manual',
            model_config_id UUID,
            aggregate_score DOUBLE PRECISION,
            result_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT evaluation_runs_status_check
                CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
            CONSTRAINT evaluation_runs_score_check
                CHECK (aggregate_score IS NULL OR aggregate_score BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_evaluation_runs_companion_status ON evaluation_runs(companion_id, status, created_at DESC)")

    op.execute(
        """
        CREATE TABLE evaluation_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            evaluation_run_id UUID NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
            evaluation_case_id UUID REFERENCES evaluation_cases(id),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            replay_id UUID REFERENCES agent_run_replays(id),
            status TEXT NOT NULL DEFAULT 'needs_review',
            score DOUBLE PRECISION,
            judge_reason TEXT,
            output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            expected_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_bad_case_id UUID,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT evaluation_results_status_check
                CHECK (status IN ('passed', 'failed', 'warning', 'needs_review', 'skipped')),
            CONSTRAINT evaluation_results_score_check
                CHECK (score IS NULL OR score BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_evaluation_results_run ON evaluation_results(evaluation_run_id)")
    op.execute("CREATE INDEX idx_evaluation_results_status ON evaluation_results(status, created_at DESC)")

    op.execute(
        """
        CREATE TABLE evaluation_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            evaluation_run_id UUID REFERENCES evaluation_runs(id) ON DELETE CASCADE,
            metric_name TEXT NOT NULL,
            metric_value DOUBLE PRECISION NOT NULL,
            metric_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT evaluation_metrics_value_check
                CHECK (metric_value BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_evaluation_metrics_run ON evaluation_metrics(evaluation_run_id)")

    op.execute(
        """
        CREATE TABLE regression_cases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            source_bad_case_id UUID REFERENCES bad_case_inbox_items(id),
            source_replay_id UUID REFERENCES agent_run_replays(id),
            title TEXT NOT NULL,
            case_type TEXT NOT NULL DEFAULT 'manual',
            input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            expected_behavior TEXT NOT NULL,
            expected_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL DEFAULT 'active',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT regression_cases_status_check
                CHECK (status IN ('active', 'disabled', 'passed', 'failed', 'needs_update', 'archived'))
        )
        """
    )
    op.execute("CREATE INDEX idx_regression_cases_companion_status ON regression_cases(companion_id, status, created_at DESC)")

    op.execute(
        """
        CREATE TABLE regression_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            status TEXT NOT NULL DEFAULT 'pending',
            total_count INTEGER NOT NULL DEFAULT 0,
            passed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            result_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT regression_runs_status_check
                CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
            CONSTRAINT regression_runs_count_check
                CHECK (total_count >= 0 AND passed_count >= 0 AND failed_count >= 0)
        )
        """
    )
    op.execute("CREATE INDEX idx_regression_runs_companion_status ON regression_runs(companion_id, status, created_at DESC)")

    op.execute(
        """
        CREATE TABLE regression_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            regression_run_id UUID NOT NULL REFERENCES regression_runs(id) ON DELETE CASCADE,
            regression_case_id UUID NOT NULL REFERENCES regression_cases(id),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            replay_id UUID REFERENCES agent_run_replays(id),
            status TEXT NOT NULL DEFAULT 'needs_review',
            score DOUBLE PRECISION,
            actual_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            failure_reason TEXT,
            created_bad_case_id UUID,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT regression_results_status_check
                CHECK (status IN ('passed', 'failed', 'warning', 'needs_review', 'skipped')),
            CONSTRAINT regression_results_score_check
                CHECK (score IS NULL OR score BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_regression_results_run ON regression_results(regression_run_id)")
    op.execute("CREATE INDEX idx_regression_results_case ON regression_results(regression_case_id)")


def downgrade() -> None:
    for table in [
        "regression_results",
        "regression_runs",
        "regression_cases",
        "evaluation_metrics",
        "evaluation_results",
        "evaluation_runs",
        "evaluation_cases",
        "evaluation_datasets",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
