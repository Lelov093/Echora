"""Backfill deterministic membership baseline evidence for existing product Rooms.

Revision ID: p5_b1_room_membership_backfill
Revises: p5_b1_room_channel_foundation
"""

from alembic import op


revision = "p5_b1_room_membership_backfill"
down_revision = "p5_b1_room_channel_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO companion_room_membership_events (
            user_id, co_presence_session_id, participant_id, companion_id,
            event_type, from_status, to_status, from_role, to_role,
            roster_revision, participant_revision, reason, evidence_json,
            occurred_at, metadata
        )
        SELECT
            participant.user_id,
            participant.co_presence_session_id,
            participant.id,
            participant.participant_companion_id,
            'invited',
            NULL,
            participant.join_status,
            NULL,
            participant.participant_role,
            room.roster_revision,
            participant.membership_revision,
            'p5_b1_existing_room_baseline',
            jsonb_build_object(
                'source', 'deterministic_backfill',
                'historical_transition_inferred', false,
                'raw_history_shared', false
            ),
            COALESCE(participant.joined_at, participant.created_at),
            jsonb_build_object('phase', 'p5_b1', 'backfilled', true)
        FROM co_presence_participants participant
        JOIN co_presence_sessions room ON room.id = participant.co_presence_session_id
        WHERE room.session_source = 'companion_home'
          AND participant.participant_type = 'companion'
          AND participant.participant_companion_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM companion_room_membership_events existing
              WHERE existing.participant_id = participant.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM companion_room_membership_events
        WHERE reason = 'p5_b1_existing_room_baseline'
          AND evidence_json->>'source' = 'deterministic_backfill'
        """
    )
