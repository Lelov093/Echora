"""phase4_01_companion_identity_schema

Revision ID: p4_01_companion_identity
Revises: p3_05_evidence_trace
Create Date: 2026-06-01 00:00:00.000000

Create Phase 4 Reoriented companion identity, persona, contract, boundary,
visibility, and lifecycle schema on top of the existing companions entity.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p4_01_companion_identity"
down_revision: Union[str, Sequence[str], None] = "p3_05_evidence_trace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROFILE_STATUS_VALUES = ("active", "paused", "archived")
PERSONA_LOCK_LEVEL_VALUES = ("flexible", "guarded", "strict")
DRIFT_GUARD_LEVEL_VALUES = ("light", "standard", "strong")
PRESENCE_STYLE_VALUES = ("quiet", "balanced", "expressive")
RELATIONSHIP_ROLE_VALUES = (
    "companion",
    "collaborator",
    "guide",
    "mentor",
    "partner",
    "specialist",
)
CONTRACT_STATUS_VALUES = ("active", "paused", "archived")
SHARED_MEMORY_POLICY_VALUES = (
    "candidate_review",
    "user_authorized_only",
    "never_auto_share",
)
CROSS_COMPANION_DISCLOSURE_VALUES = (
    "review_required",
    "explicit_user_authorization",
    "never",
)
PRIVATE_MEMORY_DEFAULT_VALUES = (
    "private_companion_only",
    "review_before_share",
    "user_authorized_only",
)
GLOBAL_MEMORY_SCOPE_VALUES = (
    "none",
    "low_risk_summary_only",
    "authorized_full",
    "task_scoped",
)
CROSS_COMPANION_READ_POLICY_VALUES = (
    "blocked",
    "review_required",
    "explicit_user_authorization",
)
PRESENCE_INTERRUPT_POLICY_VALUES = (
    "respect_existing_boundary",
    "allow_low_risk_only",
    "manual_only",
)
MEMORY_VISIBILITY_POLICY_VALUES = ("private_only", "scoped_summary", "authorized_full")
RELATIONSHIP_MEMORY_SCOPE_VALUES = ("none", "contract_scoped", "authorized_shared")
LIFECYCLE_EVENT_TYPE_VALUES = (
    "default_companion_upgraded",
    "companion_profile_backfilled",
    "identity_profile_initialized",
    "persona_profile_initialized",
    "relationship_contract_initialized",
    "boundary_profile_initialized",
    "visibility_policy_initialized",
)
LIFECYCLE_EVENT_SOURCE_VALUES = ("migration", "seed", "system", "user", "api")


def ck(table: str, column: str, values: tuple[str, ...], name: str | None = None) -> sa.CheckConstraint:
    constraint_name = name or f"{table}_{column}_check"
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=constraint_name)


def upgrade() -> None:
    op.create_table(
        "companion_identity_profiles",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("identity_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("origin_story", sa.Text(), nullable=True),
        sa.Column("self_continuity_summary", sa.Text(), nullable=True),
        sa.Column("core_traits_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("identity_labels_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("voice_style_hint", sa.Text(), nullable=True),
        sa.Column("avatar_style_hint", sa.Text(), nullable=True),
        sa.Column("profile_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.UniqueConstraint("companion_id", name="uq_companion_identity_profiles_companion_id"),
        ck("companion_identity_profiles", "profile_status", PROFILE_STATUS_VALUES, "ck_cip_status"),
    )
    op.create_index(
        "idx_companion_identity_profiles_user_companion",
        "companion_identity_profiles",
        ["user_id", "companion_id"],
    )

    op.create_table(
        "companion_persona_profiles",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("persona_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("communication_style_summary", sa.Text(), nullable=True),
        sa.Column("tone_descriptors_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("core_values_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("response_preferences_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("persona_lock_level", sa.Text(), nullable=False, server_default=sa.text("'guarded'")),
        sa.Column("drift_guard_level", sa.Text(), nullable=False, server_default=sa.text("'standard'")),
        sa.Column("presence_style", sa.Text(), nullable=False, server_default=sa.text("'balanced'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.UniqueConstraint("companion_id", name="uq_companion_persona_profiles_companion_id"),
        ck("companion_persona_profiles", "persona_lock_level", PERSONA_LOCK_LEVEL_VALUES, "ck_cpp_lock"),
        ck("companion_persona_profiles", "drift_guard_level", DRIFT_GUARD_LEVEL_VALUES, "ck_cpp_drift"),
        ck("companion_persona_profiles", "presence_style", PRESENCE_STYLE_VALUES, "ck_cpp_presence"),
    )
    op.create_index(
        "idx_companion_persona_profiles_user_companion",
        "companion_persona_profiles",
        ["user_id", "companion_id"],
    )

    op.create_table(
        "companion_relationship_contracts",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("relationship_role", sa.Text(), nullable=False, server_default=sa.text("'companion'")),
        sa.Column("contract_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("contract_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("collaboration_style_summary", sa.Text(), nullable=True),
        sa.Column("support_scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("shared_memory_policy", sa.Text(), nullable=False, server_default=sa.text("'candidate_review'")),
        sa.Column("cross_companion_disclosure_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("contract_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.UniqueConstraint("companion_id", name="uq_companion_relationship_contracts_companion_id"),
        ck("companion_relationship_contracts", "relationship_role", RELATIONSHIP_ROLE_VALUES, "ck_crc_role"),
        ck("companion_relationship_contracts", "contract_status", CONTRACT_STATUS_VALUES, "ck_crc_status"),
        ck("companion_relationship_contracts", "shared_memory_policy", SHARED_MEMORY_POLICY_VALUES, "ck_crc_shared"),
        ck(
            "companion_relationship_contracts",
            "cross_companion_disclosure_policy",
            CROSS_COMPANION_DISCLOSURE_VALUES,
            "ck_crc_disclosure",
        ),
    )
    op.create_index(
        "idx_companion_relationship_contracts_user_companion",
        "companion_relationship_contracts",
        ["user_id", "companion_id"],
    )

    op.create_table(
        "companion_boundary_profiles",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("boundary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("private_memory_default", sa.Text(), nullable=False, server_default=sa.text("'private_companion_only'")),
        sa.Column("shared_memory_default", sa.Text(), nullable=False, server_default=sa.text("'candidate_review'")),
        sa.Column("global_memory_read_scope", sa.Text(), nullable=False, server_default=sa.text("'low_risk_summary_only'")),
        sa.Column("cross_companion_read_policy", sa.Text(), nullable=False, server_default=sa.text("'blocked'")),
        sa.Column("review_required_private_to_shared", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("review_required_shared_to_private", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("review_required_cross_companion_share", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("presence_interrupt_policy", sa.Text(), nullable=False, server_default=sa.text("'respect_existing_boundary'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.UniqueConstraint("companion_id", name="uq_companion_boundary_profiles_companion_id"),
        ck("companion_boundary_profiles", "private_memory_default", PRIVATE_MEMORY_DEFAULT_VALUES, "ck_cbp_private"),
        ck("companion_boundary_profiles", "shared_memory_default", SHARED_MEMORY_POLICY_VALUES, "ck_cbp_shared"),
        ck("companion_boundary_profiles", "global_memory_read_scope", GLOBAL_MEMORY_SCOPE_VALUES, "ck_cbp_scope"),
        ck(
            "companion_boundary_profiles",
            "cross_companion_read_policy",
            CROSS_COMPANION_READ_POLICY_VALUES,
            "ck_cbp_cross_read",
        ),
        ck(
            "companion_boundary_profiles",
            "presence_interrupt_policy",
            PRESENCE_INTERRUPT_POLICY_VALUES,
            "ck_cbp_presence",
        ),
    )
    op.create_index(
        "idx_companion_boundary_profiles_user_companion",
        "companion_boundary_profiles",
        ["user_id", "companion_id"],
    )

    op.create_table(
        "companion_visibility_policies",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("memory_visibility_policy", sa.Text(), nullable=False, server_default=sa.text("'scoped_summary'")),
        sa.Column("user_global_memory_scope", sa.Text(), nullable=False, server_default=sa.text("'low_risk_summary_only'")),
        sa.Column("relationship_memory_scope", sa.Text(), nullable=False, server_default=sa.text("'contract_scoped'")),
        sa.Column("allow_low_risk_summary_read", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_authorized_global_read", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_sensitive_global_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_other_companion_private_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("visibility_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.UniqueConstraint("companion_id", name="uq_companion_visibility_policies_companion_id"),
        ck(
            "companion_visibility_policies",
            "memory_visibility_policy",
            MEMORY_VISIBILITY_POLICY_VALUES,
            "ck_cvp_visibility",
        ),
        ck(
            "companion_visibility_policies",
            "user_global_memory_scope",
            GLOBAL_MEMORY_SCOPE_VALUES,
            "ck_cvp_global_scope",
        ),
        ck(
            "companion_visibility_policies",
            "relationship_memory_scope",
            RELATIONSHIP_MEMORY_SCOPE_VALUES,
            "ck_cvp_rel_scope",
        ),
    )
    op.create_index(
        "idx_companion_visibility_policies_user_companion",
        "companion_visibility_policies",
        ["user_id", "companion_id"],
    )

    op.create_table(
        "companion_lifecycle_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_source", sa.Text(), nullable=False, server_default=sa.text("'migration'")),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("previous_state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("new_state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        ck("companion_lifecycle_events", "event_type", LIFECYCLE_EVENT_TYPE_VALUES, "ck_cle_event_type"),
        ck("companion_lifecycle_events", "event_source", LIFECYCLE_EVENT_SOURCE_VALUES, "ck_cle_event_source"),
    )
    op.create_index(
        "idx_companion_lifecycle_events_companion_created",
        "companion_lifecycle_events",
        ["companion_id", "created_at"],
    )
    op.create_index(
        "idx_companion_lifecycle_events_type_created",
        "companion_lifecycle_events",
        ["event_type", "created_at"],
    )

    op.execute(
        """
        INSERT INTO companion_identity_profiles (
            user_id,
            companion_id,
            display_name,
            identity_summary,
            origin_story,
            self_continuity_summary,
            core_traits_json,
            identity_labels_json,
            voice_style_hint,
            avatar_style_hint,
            profile_status,
            metadata
        )
        SELECT
            c.user_id,
            c.id,
            COALESCE(NULLIF(c.name, ''), 'Companion'),
            COALESCE(
                NULLIF(c.identity_prompt, ''),
                NULLIF(c.subtitle, ''),
                'Identity profile pending refinement.'
            ),
            NULLIF(c.companion_profile->>'origin_story', ''),
            COALESCE(NULLIF(c.subtitle, ''), 'Self continuity summary pending refinement.'),
            CASE
                WHEN jsonb_typeof(c.companion_profile->'core_traits') = 'array'
                    THEN c.companion_profile->'core_traits'
                ELSE '[]'::jsonb
            END,
            CASE
                WHEN jsonb_typeof(c.companion_profile->'identity_labels') = 'array'
                    THEN c.companion_profile->'identity_labels'
                ELSE '[]'::jsonb
            END,
            NULLIF(c.companion_profile->>'voice_style_hint', ''),
            NULLIF(c.companion_profile->>'avatar_style_hint', ''),
            'active',
            jsonb_build_object(
                'source', 'phase4_r1_migration',
                'legacy_companion_profile', COALESCE(c.companion_profile, '{}'::jsonb)
            )
        FROM companions c
        LEFT JOIN companion_identity_profiles ip ON ip.companion_id = c.id
        WHERE ip.id IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO companion_persona_profiles (
            user_id,
            companion_id,
            persona_summary,
            communication_style_summary,
            tone_descriptors_json,
            core_values_json,
            response_preferences_json,
            persona_lock_level,
            drift_guard_level,
            presence_style,
            metadata
        )
        SELECT
            c.user_id,
            c.id,
            COALESCE(
                NULLIF(c.base_personality, ''),
                NULLIF(c.identity_prompt, ''),
                'Persona profile pending refinement.'
            ),
            NULLIF(c.companion_profile->>'communication_style_summary', ''),
            CASE
                WHEN jsonb_typeof(c.tone_profile->'descriptors') = 'array'
                    THEN c.tone_profile->'descriptors'
                ELSE '[]'::jsonb
            END,
            CASE
                WHEN jsonb_typeof(c.companion_profile->'core_values') = 'array'
                    THEN c.companion_profile->'core_values'
                ELSE '[]'::jsonb
            END,
            COALESCE(c.tone_profile, '{}'::jsonb),
            COALESCE(NULLIF(c.companion_profile->>'persona_lock_level', ''), 'guarded'),
            COALESCE(NULLIF(c.companion_profile->>'drift_guard_level', ''), 'standard'),
            COALESCE(NULLIF(c.companion_profile->>'presence_style', ''), 'balanced'),
            jsonb_build_object(
                'source', 'phase4_r1_migration',
                'legacy_tone_profile', COALESCE(c.tone_profile, '{}'::jsonb)
            )
        FROM companions c
        LEFT JOIN companion_persona_profiles pp ON pp.companion_id = c.id
        WHERE pp.id IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO companion_relationship_contracts (
            user_id,
            companion_id,
            relationship_role,
            contract_status,
            contract_summary,
            collaboration_style_summary,
            support_scope_json,
            shared_memory_policy,
            cross_companion_disclosure_policy,
            contract_json,
            metadata
        )
        SELECT
            c.user_id,
            c.id,
            COALESCE(NULLIF(c.companion_profile->>'relationship_role', ''), 'companion'),
            'active',
            COALESCE(
                NULLIF(rs.summary, ''),
                NULLIF(c.subtitle, ''),
                'Long-term companion contract pending refinement.'
            ),
            NULLIF(c.companion_profile->>'collaboration_style_summary', ''),
            CASE
                WHEN jsonb_typeof(c.companion_profile->'support_scope') = 'array'
                    THEN c.companion_profile->'support_scope'
                ELSE '[]'::jsonb
            END,
            'candidate_review',
            'review_required',
            jsonb_build_object(
                'relationship_state_summary', COALESCE(rs.summary, ''),
                'legacy_companion_profile', COALESCE(c.companion_profile, '{}'::jsonb)
            ),
            jsonb_build_object('source', 'phase4_r1_migration')
        FROM companions c
        LEFT JOIN relationship_states rs
            ON rs.user_id = c.user_id AND rs.companion_id = c.id
        LEFT JOIN companion_relationship_contracts rc ON rc.companion_id = c.id
        WHERE rc.id IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO companion_boundary_profiles (
            user_id,
            companion_id,
            boundary_json,
            private_memory_default,
            shared_memory_default,
            global_memory_read_scope,
            cross_companion_read_policy,
            review_required_private_to_shared,
            review_required_shared_to_private,
            review_required_cross_companion_share,
            presence_interrupt_policy,
            metadata
        )
        SELECT
            c.user_id,
            c.id,
            jsonb_build_object(
                'legacy_boundary_rules', COALESCE(bs.boundary_rules, '{}'::jsonb),
                'legacy_quiet_hours', COALESCE(bs.quiet_hours, '{}'::jsonb),
                'legacy_memory_confirmation_policy', COALESCE(bs.memory_confirmation_policy, '{}'::jsonb),
                'legacy_growth_confirmation_policy', COALESCE(bs.growth_confirmation_policy, '{}'::jsonb),
                'legacy_feedback_usage_policy', COALESCE(bs.feedback_usage_policy, '{}'::jsonb)
            ),
            'private_companion_only',
            'candidate_review',
            'low_risk_summary_only',
            'blocked',
            true,
            true,
            true,
            'respect_existing_boundary',
            jsonb_build_object(
                'source', 'phase4_r1_migration',
                'legacy_boundary_setting_id', bs.id
            )
        FROM companions c
        LEFT JOIN boundary_settings bs
            ON bs.user_id = c.user_id AND bs.companion_id = c.id
        LEFT JOIN companion_boundary_profiles bp ON bp.companion_id = c.id
        WHERE bp.id IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO companion_visibility_policies (
            user_id,
            companion_id,
            memory_visibility_policy,
            user_global_memory_scope,
            relationship_memory_scope,
            allow_low_risk_summary_read,
            allow_authorized_global_read,
            allow_sensitive_global_read,
            allow_other_companion_private_read,
            visibility_rules_json,
            metadata
        )
        SELECT
            c.user_id,
            c.id,
            'scoped_summary',
            'low_risk_summary_only',
            'contract_scoped',
            true,
            true,
            false,
            false,
            COALESCE(bs.continuity_visibility_policy, '{}'::jsonb),
            jsonb_build_object(
                'source', 'phase4_r1_migration',
                'legacy_continuity_visibility_policy', COALESCE(bs.continuity_visibility_policy, '{}'::jsonb)
            )
        FROM companions c
        LEFT JOIN boundary_settings bs
            ON bs.user_id = c.user_id AND bs.companion_id = c.id
        LEFT JOIN companion_visibility_policies vp ON vp.companion_id = c.id
        WHERE vp.id IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO companion_lifecycle_events (
            user_id,
            companion_id,
            event_type,
            event_source,
            title,
            detail,
            previous_state_json,
            new_state_json,
            review_required,
            occurred_at,
            metadata
        )
        SELECT
            c.user_id,
            c.id,
            CASE
                WHEN c.name = 'Echora' THEN 'default_companion_upgraded'
                ELSE 'companion_profile_backfilled'
            END,
            'migration',
            CASE
                WHEN c.name = 'Echora' THEN 'Default companion upgraded to Phase 4 identity schema'
                ELSE 'Existing companion backfilled into Phase 4 identity schema'
            END,
            'Created identity, persona, contract, boundary, and visibility extension rows.',
            '{}'::jsonb,
            jsonb_build_object(
                'identity_profile_created', true,
                'persona_profile_created', true,
                'relationship_contract_created', true,
                'boundary_profile_created', true,
                'visibility_policy_created', true
            ),
            false,
            now(),
            jsonb_build_object(
                'source', 'phase4_r1_migration',
                'companion_name', c.name
            )
        FROM companions c
        LEFT JOIN companion_lifecycle_events le
            ON le.companion_id = c.id
           AND le.event_source = 'migration'
           AND le.event_type IN ('default_companion_upgraded', 'companion_profile_backfilled')
        WHERE le.id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_companion_lifecycle_events_type_created", table_name="companion_lifecycle_events")
    op.drop_index("idx_companion_lifecycle_events_companion_created", table_name="companion_lifecycle_events")
    op.drop_table("companion_lifecycle_events")

    op.drop_index("idx_companion_visibility_policies_user_companion", table_name="companion_visibility_policies")
    op.drop_table("companion_visibility_policies")

    op.drop_index("idx_companion_boundary_profiles_user_companion", table_name="companion_boundary_profiles")
    op.drop_table("companion_boundary_profiles")

    op.drop_index("idx_companion_relationship_contracts_user_companion", table_name="companion_relationship_contracts")
    op.drop_table("companion_relationship_contracts")

    op.drop_index("idx_companion_persona_profiles_user_companion", table_name="companion_persona_profiles")
    op.drop_table("companion_persona_profiles")

    op.drop_index("idx_companion_identity_profiles_user_companion", table_name="companion_identity_profiles")
    op.drop_table("companion_identity_profiles")
