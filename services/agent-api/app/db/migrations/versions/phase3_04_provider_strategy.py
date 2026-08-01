"""phase3_04_provider_strategy

Revision ID: p3_04_provider_strategy
Revises: p3_03_evaluation_regression
Create Date: 2026-05-31 00:00:00.000000

Create Phase 3 Provider, Prompt, LLM Call, and Strategy Learning schema.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "p3_04_provider_strategy"
down_revision: Union[str, Sequence[str], None] = "p3_03_eval_regression"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE llm_provider_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id),
            companion_id UUID REFERENCES companions(id),
            provider_name TEXT NOT NULL,
            provider_type TEXT NOT NULL DEFAULT 'llm',
            status TEXT NOT NULL DEFAULT 'enabled',
            base_url TEXT,
            env_key_name TEXT,
            config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT llm_provider_configs_type_check
                CHECK (provider_type IN ('llm', 'embedding', 'reranker', 'vision', 'tool')),
            CONSTRAINT llm_provider_configs_status_check
                CHECK (status IN ('enabled', 'disabled', 'degraded', 'failed'))
        )
        """
    )
    op.execute("CREATE INDEX idx_llm_provider_configs_companion_status ON llm_provider_configs(companion_id, status)")

    op.execute(
        """
        CREATE TABLE llm_model_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider_config_id UUID REFERENCES llm_provider_configs(id),
            model_name TEXT NOT NULL,
            model_role TEXT NOT NULL DEFAULT 'response_generation',
            status TEXT NOT NULL DEFAULT 'enabled',
            max_tokens INTEGER,
            temperature DOUBLE PRECISION,
            config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT llm_model_configs_status_check
                CHECK (status IN ('enabled', 'disabled', 'degraded', 'failed')),
            CONSTRAINT llm_model_configs_temperature_check
                CHECK (temperature IS NULL OR temperature BETWEEN 0 AND 2)
        )
        """
    )
    op.execute("CREATE INDEX idx_llm_model_configs_provider_status ON llm_model_configs(provider_config_id, status)")

    op.execute(
        """
        CREATE TABLE prompt_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id),
            companion_id UUID REFERENCES companions(id),
            prompt_key TEXT NOT NULL,
            version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            content TEXT NOT NULL,
            change_note TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT prompt_versions_status_check
                CHECK (status IN ('draft', 'active', 'archived', 'deprecated'))
        )
        """
    )
    op.execute("CREATE INDEX idx_prompt_versions_key_status ON prompt_versions(prompt_key, status)")

    op.execute(
        """
        CREATE TABLE llm_call_records (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id),
            companion_id UUID REFERENCES companions(id),
            conversation_id UUID REFERENCES conversations(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            trace_step_id UUID REFERENCES trace_steps(id),
            provider_config_id UUID REFERENCES llm_provider_configs(id),
            model_config_id UUID REFERENCES llm_model_configs(id),
            prompt_version_id UUID REFERENCES prompt_versions(id),
            status TEXT NOT NULL DEFAULT 'queued',
            purpose TEXT NOT NULL DEFAULT 'response_generation',
            input_summary TEXT,
            output_summary TEXT,
            token_input INTEGER,
            token_output INTEGER,
            latency_ms INTEGER,
            fallback_used BOOLEAN NOT NULL DEFAULT false,
            error_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT llm_call_records_status_check
                CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'rate_limited', 'fallback_used')),
            CONSTRAINT llm_call_records_token_check
                CHECK ((token_input IS NULL OR token_input >= 0) AND (token_output IS NULL OR token_output >= 0)),
            CONSTRAINT llm_call_records_latency_check
                CHECK (latency_ms IS NULL OR latency_ms >= 0)
        )
        """
    )
    op.execute("CREATE INDEX idx_llm_call_records_trace ON llm_call_records(trace_run_id)")
    op.execute("CREATE INDEX idx_llm_call_records_companion_created ON llm_call_records(companion_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE fallback_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id),
            companion_id UUID REFERENCES companions(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            llm_call_record_id UUID REFERENCES llm_call_records(id),
            from_provider_config_id UUID REFERENCES llm_provider_configs(id),
            to_provider_config_id UUID REFERENCES llm_provider_configs(id),
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'recorded',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_fallback_events_trace_created ON fallback_events(trace_run_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE reranker_training_examples (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            memory_id UUID REFERENCES memories(id),
            feedback_event_id UUID REFERENCES feedback_events(id),
            memory_usage_event_id UUID REFERENCES memory_usage_events(id),
            label DOUBLE PRECISION NOT NULL,
            feature_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            source_type TEXT NOT NULL DEFAULT 'feedback',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT reranker_training_examples_label_check
                CHECK (label BETWEEN -1 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_reranker_training_examples_companion_created ON reranker_training_examples(companion_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE memory_reranker_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            conversation_id UUID REFERENCES conversations(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            learning_mode TEXT NOT NULL DEFAULT 'shadow',
            status TEXT NOT NULL DEFAULT 'completed',
            candidate_memory_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
            selected_memory_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
            score_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            explanation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT memory_reranker_runs_learning_mode_check
                CHECK (learning_mode IN ('disabled', 'shadow', 'assistive', 'active')),
            CONSTRAINT memory_reranker_runs_status_check
                CHECK (status IN ('created', 'completed', 'failed', 'cancelled'))
        )
        """
    )
    op.execute("CREATE INDEX idx_memory_reranker_runs_trace ON memory_reranker_runs(trace_run_id)")

    op.execute(
        """
        CREATE TABLE presence_policy_feedback_samples (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            presence_opportunity_id UUID REFERENCES presence_opportunities(id),
            feedback_event_id UUID REFERENCES feedback_events(id),
            action_taken TEXT NOT NULL,
            reward DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            feature_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT presence_policy_feedback_samples_reward_check
                CHECK (reward BETWEEN -1 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_presence_policy_feedback_samples_companion_created ON presence_policy_feedback_samples(companion_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE presence_policy_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            companion_id UUID NOT NULL REFERENCES companions(id),
            conversation_id UUID REFERENCES conversations(id),
            trace_run_id UUID REFERENCES trace_runs(id),
            presence_opportunity_id UUID REFERENCES presence_opportunities(id),
            learning_mode TEXT NOT NULL DEFAULT 'shadow',
            action_space TEXT[] NOT NULL DEFAULT ARRAY['no_show', 'defer', 'queue']::text[],
            selected_action TEXT NOT NULL DEFAULT 'no_show',
            reward_prediction DOUBLE PRECISION,
            explanation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            CONSTRAINT presence_policy_runs_learning_mode_check
                CHECK (learning_mode IN ('disabled', 'shadow', 'assistive', 'active')),
            CONSTRAINT presence_policy_runs_reward_prediction_check
                CHECK (reward_prediction IS NULL OR reward_prediction BETWEEN -1 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX idx_presence_policy_runs_trace ON presence_policy_runs(trace_run_id)")
    op.execute("CREATE INDEX idx_presence_policy_runs_opportunity ON presence_policy_runs(presence_opportunity_id)")


def downgrade() -> None:
    for table in [
        "presence_policy_runs",
        "presence_policy_feedback_samples",
        "memory_reranker_runs",
        "reranker_training_examples",
        "fallback_events",
        "llm_call_records",
        "prompt_versions",
        "llm_model_configs",
        "llm_provider_configs",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
