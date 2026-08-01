"""phase4_02_companion_memory_schema

Revision ID: p4_02_companion_memory
Revises: p4_01_companion_identity
Create Date: 2026-06-01 00:00:00.000000

Create Phase 4 Reoriented companion-private/shared-memory/review schema and
enhance existing memory tables without rewriting legacy memory meaning.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p4_02_companion_memory"
down_revision: Union[str, Sequence[str], None] = "p4_01_companion_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MEMORY_SCOPE_TYPE_VALUES = (
    "legacy_private",
    "private_companion",
    "relationship",
    "shared_candidate",
    "shared_episodic",
)
COMPANION_SCOPE_VALUES = ("private_companion", "relationship", "shared_scene", "shared_group")
SCOPE_STATUS_VALUES = ("active", "paused", "archived")
SCOPE_WRITE_POLICY_VALUES = ("private_only", "candidate_review", "explicit_user_authorization")
LINK_STATUS_VALUES = ("active", "suppressed", "archived")
SHARED_MEMORY_STATUS_VALUES = ("draft", "active", "archived")
SHARED_MEMORY_SOURCE_VALUES = ("candidate_review", "co_presence", "manual", "review_approved")
SHARED_MEMORY_CANDIDATE_STATUS_VALUES = (
    "pending_review",
    "approved",
    "rejected",
    "merged",
    "expired",
)
PARTICIPANT_TYPE_VALUES = ("user", "companion")
PARTICIPANT_ROLE_VALUES = ("owner", "active", "observing")
PRIVATE_SYNC_POLICY_VALUES = ("none", "review_required", "explicit_user_authorization")
CROSS_MEMORY_EVENT_TYPE_VALUES = (
    "read_request",
    "share_request",
    "share_granted",
    "share_denied",
    "private_to_shared_request",
    "shared_to_private_request",
)
CROSS_MEMORY_EVENT_STATUS_VALUES = ("pending_review", "approved", "rejected", "recorded")
REVIEW_DECISION_VALUES = ("pending", "approved", "rejected", "edited")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def upgrade() -> None:
    op.create_table(
        "companion_memory_scopes",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False, server_default=sa.text("'private_companion'")),
        sa.Column("scope_key", sa.Text(), nullable=False, server_default=sa.text("'default'")),
        sa.Column("title", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("default_write_policy", sa.Text(), nullable=False, server_default=sa.text("'private_only'")),
        sa.Column("visibility_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.UniqueConstraint("companion_id", "scope_type", "scope_key", name="uq_cms_companion_scope"),
        ck("scope_type", COMPANION_SCOPE_VALUES, "ck_cms_scope_type"),
        ck("scope_status", SCOPE_STATUS_VALUES, "ck_cms_status"),
        ck("default_write_policy", SCOPE_WRITE_POLICY_VALUES, "ck_cms_write"),
    )
    op.create_index("idx_cms_companion_scope", "companion_memory_scopes", ["companion_id", "scope_type", "scope_key"])

    op.create_table(
        "shared_episodic_memories",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("source_type", sa.Text(), nullable=False, server_default=sa.text("'candidate_review'")),
        sa.Column("visibility_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("scene_context_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        ck("status", SHARED_MEMORY_STATUS_VALUES, "ck_sem_status"),
        ck("source_type", SHARED_MEMORY_SOURCE_VALUES, "ck_sem_source"),
    )
    op.create_index("idx_sem_user_status", "shared_episodic_memories", ["user_id", "status", "created_at"])

    op.add_column("memories", sa.Column("owner_companion_id", postgresql.UUID, nullable=True))
    op.add_column(
        "memories",
        sa.Column(
            "memory_scope_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'legacy_private'"),
        ),
    )
    op.add_column("memories", sa.Column("shared_memory_id", postgresql.UUID, nullable=True))
    op.add_column(
        "memories",
        sa.Column(
            "visibility_policy_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_foreign_key("fk_memories_owner_companion_id", "memories", "companions", ["owner_companion_id"], ["id"])
    op.create_foreign_key("fk_memories_shared_memory_id", "memories", "shared_episodic_memories", ["shared_memory_id"], ["id"])
    op.execute(
        "ALTER TABLE memories ADD CONSTRAINT ck_mem_scope_type "
        "CHECK (memory_scope_type IN ('legacy_private', 'private_companion', 'relationship', 'shared_candidate', 'shared_episodic'))"
    )
    op.execute("UPDATE memories SET owner_companion_id = companion_id WHERE owner_companion_id IS NULL")
    op.create_index("idx_memories_owner_scope", "memories", ["owner_companion_id", "memory_scope_type"])
    op.create_index("idx_memories_shared_memory", "memories", ["shared_memory_id"])

    op.add_column("memory_candidates", sa.Column("proposed_owner_companion_id", postgresql.UUID, nullable=True))
    op.add_column("memory_candidates", sa.Column("proposed_shared_memory_id", postgresql.UUID, nullable=True))
    op.add_column(
        "memory_candidates",
        sa.Column(
            "requires_companion_memory_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_foreign_key(
        "fk_memory_candidates_proposed_owner_companion_id",
        "memory_candidates",
        "companions",
        ["proposed_owner_companion_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_memory_candidates_proposed_shared_memory_id",
        "memory_candidates",
        "shared_episodic_memories",
        ["proposed_shared_memory_id"],
        ["id"],
    )
    op.execute(
        "UPDATE memory_candidates SET proposed_owner_companion_id = companion_id "
        "WHERE proposed_owner_companion_id IS NULL"
    )
    op.create_index("idx_mc_proposed_owner", "memory_candidates", ["proposed_owner_companion_id"])
    op.create_index("idx_mc_proposed_shared", "memory_candidates", ["proposed_shared_memory_id"])

    op.create_table(
        "companion_private_memory_links",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("memory_id", postgresql.UUID, nullable=False),
        sa.Column("memory_scope_id", postgresql.UUID, nullable=False),
        sa.Column("link_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"]),
        sa.ForeignKeyConstraint(["memory_scope_id"], ["companion_memory_scopes.id"]),
        sa.UniqueConstraint("companion_id", "memory_id", name="uq_cpml_companion_memory"),
        ck("link_status", LINK_STATUS_VALUES, "ck_cpml_status"),
    )
    op.create_index("idx_cpml_companion_memory", "companion_private_memory_links", ["companion_id", "memory_id"])

    op.create_table(
        "relationship_memory_links",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("related_companion_id", postgresql.UUID, nullable=True),
        sa.Column("memory_id", postgresql.UUID, nullable=False),
        sa.Column("relationship_contract_id", postgresql.UUID, nullable=False),
        sa.Column("link_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["related_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"]),
        sa.ForeignKeyConstraint(["relationship_contract_id"], ["companion_relationship_contracts.id"]),
        sa.UniqueConstraint("memory_id", "relationship_contract_id", name="uq_rml_memory_contract"),
        ck("link_status", LINK_STATUS_VALUES, "ck_rml_status"),
    )
    op.create_index("idx_rml_contract_memory", "relationship_memory_links", ["relationship_contract_id", "memory_id"])

    op.create_table(
        "shared_memory_candidates",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("source_memory_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("source_memory_id", postgresql.UUID, nullable=True),
        sa.Column("proposed_shared_memory_id", postgresql.UUID, nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("candidate_status", sa.Text(), nullable=False, server_default=sa.text("'pending_review'")),
        sa.Column("requires_user_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("candidate_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_memory_candidate_id"], ["memory_candidates.id"]),
        sa.ForeignKeyConstraint(["source_memory_id"], ["memories.id"]),
        sa.ForeignKeyConstraint(["proposed_shared_memory_id"], ["shared_episodic_memories.id"]),
        ck("candidate_status", SHARED_MEMORY_CANDIDATE_STATUS_VALUES, "ck_smc_status"),
    )
    op.create_index("idx_smc_user_status", "shared_memory_candidates", ["user_id", "candidate_status", "created_at"])

    op.create_table(
        "shared_memory_participants",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("shared_memory_id", postgresql.UUID, nullable=False),
        sa.Column("participant_type", sa.Text(), nullable=False),
        sa.Column("participant_user_id", postgresql.UUID, nullable=True),
        sa.Column("participant_companion_id", postgresql.UUID, nullable=True),
        sa.Column("participant_role", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("private_memory_sync_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["shared_memory_id"], ["shared_episodic_memories.id"]),
        sa.ForeignKeyConstraint(["participant_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["participant_companion_id"], ["companions.id"]),
        ck("participant_type", PARTICIPANT_TYPE_VALUES, "ck_smp_type"),
        ck("participant_role", PARTICIPANT_ROLE_VALUES, "ck_smp_role"),
        ck("private_memory_sync_policy", PRIVATE_SYNC_POLICY_VALUES, "ck_smp_sync"),
        sa.CheckConstraint(
            "("
            "(participant_type = 'user' AND participant_user_id IS NOT NULL AND participant_companion_id IS NULL)"
            " OR "
            "(participant_type = 'companion' AND participant_user_id IS NULL AND participant_companion_id IS NOT NULL)"
            ")",
            name="ck_smp_subject",
        ),
    )
    op.create_index("idx_smp_shared_role", "shared_memory_participants", ["shared_memory_id", "participant_role"])

    op.create_table(
        "cross_companion_memory_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("source_companion_id", postgresql.UUID, nullable=False),
        sa.Column("target_companion_id", postgresql.UUID, nullable=False),
        sa.Column("memory_id", postgresql.UUID, nullable=True),
        sa.Column("shared_memory_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending_review'")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["target_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"]),
        sa.ForeignKeyConstraint(["shared_memory_id"], ["shared_episodic_memories.id"]),
        ck("event_type", CROSS_MEMORY_EVENT_TYPE_VALUES, "ck_ccme_type"),
        ck("status", CROSS_MEMORY_EVENT_STATUS_VALUES, "ck_ccme_status"),
        sa.CheckConstraint("(memory_id IS NOT NULL OR shared_memory_id IS NOT NULL)", name="ck_ccme_target"),
    )
    op.create_index(
        "idx_ccme_source_target",
        "cross_companion_memory_events",
        ["source_companion_id", "target_companion_id", "created_at"],
    )

    op.create_table(
        "cross_companion_memory_reviews",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("cross_companion_memory_event_id", postgresql.UUID, nullable=False),
        sa.Column("decision", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("approved_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cross_companion_memory_event_id"], ["cross_companion_memory_events.id"]),
        ck("decision", REVIEW_DECISION_VALUES, "ck_ccmr_decision"),
    )
    op.create_index("idx_ccmr_event", "cross_companion_memory_reviews", ["cross_companion_memory_event_id"])

    op.create_table(
        "private_to_shared_memory_reviews",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("source_companion_id", postgresql.UUID, nullable=False),
        sa.Column("memory_id", postgresql.UUID, nullable=False),
        sa.Column("shared_memory_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("target_shared_memory_id", postgresql.UUID, nullable=True),
        sa.Column("decision", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"]),
        sa.ForeignKeyConstraint(["shared_memory_candidate_id"], ["shared_memory_candidates.id"]),
        sa.ForeignKeyConstraint(["target_shared_memory_id"], ["shared_episodic_memories.id"]),
        ck("decision", REVIEW_DECISION_VALUES, "ck_psmr_decision"),
    )
    op.create_index("idx_psmr_memory_decision", "private_to_shared_memory_reviews", ["memory_id", "decision"])

    op.create_table(
        "shared_to_private_memory_reviews",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("target_companion_id", postgresql.UUID, nullable=False),
        sa.Column("shared_memory_id", postgresql.UUID, nullable=False),
        sa.Column("target_memory_id", postgresql.UUID, nullable=True),
        sa.Column("decision", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["shared_memory_id"], ["shared_episodic_memories.id"]),
        sa.ForeignKeyConstraint(["target_memory_id"], ["memories.id"]),
        ck("decision", REVIEW_DECISION_VALUES, "ck_stpmr_decision"),
    )
    op.create_index(
        "idx_stpmr_shared_target",
        "shared_to_private_memory_reviews",
        ["shared_memory_id", "target_companion_id"],
    )

    op.execute(
        """
        INSERT INTO companion_memory_scopes (
            user_id,
            companion_id,
            scope_type,
            scope_key,
            title,
            description,
            scope_status,
            default_write_policy,
            visibility_policy_json,
            metadata
        )
        SELECT
            c.user_id,
            c.id,
            'private_companion',
            'default',
            c.name || ' private memory',
            'Default independent private memory scope for this companion.',
            'active',
            'private_only',
            jsonb_build_object(
                'memory_visibility_policy', COALESCE(vp.memory_visibility_policy, 'scoped_summary'),
                'user_global_memory_scope', COALESCE(vp.user_global_memory_scope, 'low_risk_summary_only')
            ),
            jsonb_build_object('source', 'phase4_r2_migration')
        FROM companions c
        LEFT JOIN companion_visibility_policies vp ON vp.companion_id = c.id
        LEFT JOIN companion_memory_scopes cms
            ON cms.companion_id = c.id
           AND cms.scope_type = 'private_companion'
           AND cms.scope_key = 'default'
        WHERE cms.id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_stpmr_shared_target", table_name="shared_to_private_memory_reviews")
    op.drop_table("shared_to_private_memory_reviews")

    op.drop_index("idx_psmr_memory_decision", table_name="private_to_shared_memory_reviews")
    op.drop_table("private_to_shared_memory_reviews")

    op.drop_index("idx_ccmr_event", table_name="cross_companion_memory_reviews")
    op.drop_table("cross_companion_memory_reviews")

    op.drop_index("idx_ccme_source_target", table_name="cross_companion_memory_events")
    op.drop_table("cross_companion_memory_events")

    op.drop_index("idx_smp_shared_role", table_name="shared_memory_participants")
    op.drop_table("shared_memory_participants")

    op.drop_index("idx_smc_user_status", table_name="shared_memory_candidates")
    op.drop_table("shared_memory_candidates")

    op.drop_index("idx_rml_contract_memory", table_name="relationship_memory_links")
    op.drop_table("relationship_memory_links")

    op.drop_index("idx_cpml_companion_memory", table_name="companion_private_memory_links")
    op.drop_table("companion_private_memory_links")

    op.drop_index("idx_mc_proposed_shared", table_name="memory_candidates")
    op.drop_index("idx_mc_proposed_owner", table_name="memory_candidates")
    op.drop_constraint("fk_memory_candidates_proposed_shared_memory_id", "memory_candidates", type_="foreignkey")
    op.drop_constraint("fk_memory_candidates_proposed_owner_companion_id", "memory_candidates", type_="foreignkey")
    op.drop_column("memory_candidates", "requires_companion_memory_review")
    op.drop_column("memory_candidates", "proposed_shared_memory_id")
    op.drop_column("memory_candidates", "proposed_owner_companion_id")

    op.drop_index("idx_memories_shared_memory", table_name="memories")
    op.drop_index("idx_memories_owner_scope", table_name="memories")
    op.drop_constraint("ck_mem_scope_type", "memories", type_="check")
    op.drop_constraint("fk_memories_shared_memory_id", "memories", type_="foreignkey")
    op.drop_constraint("fk_memories_owner_companion_id", "memories", type_="foreignkey")
    op.drop_column("memories", "visibility_policy_json")
    op.drop_column("memories", "shared_memory_id")
    op.drop_column("memories", "memory_scope_type")
    op.drop_column("memories", "owner_companion_id")

    op.drop_index("idx_sem_user_status", table_name="shared_episodic_memories")
    op.drop_table("shared_episodic_memories")

    op.drop_index("idx_cms_companion_scope", table_name="companion_memory_scopes")
    op.drop_table("companion_memory_scopes")
