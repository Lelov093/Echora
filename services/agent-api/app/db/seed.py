"""Core conversation Seed Data

Creates default User, Echora Companion, Companion Modes, and Boundary Settings.
Idempotent — safe to run multiple times without creating duplicates.

Usage:
    cd services/agent-api
    uv run python -m app.db.seed
"""

import sys

if sys.platform == "win32":
    import asyncio

    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    User,
    Companion,
    CompanionMode,
    BoundarySetting,
)

# ── Global enum dictionary ModeKey (without "voice") ─────────────────
# Per docs/Echora 全局类型与枚举字典 V1.txt §3.1:
# ModeKey = project | creative | daily | learning | game | character | virtual_world
MODES_TO_SEED = [
    {"mode_key": "project", "display_name": "Project Companion", "description": "Project planning and execution companion.", "is_enabled": True},
    {"mode_key": "creative", "display_name": "Creative Companion", "description": "Creative writing and worldbuilding companion.", "is_enabled": True},
    {"mode_key": "daily", "display_name": "Daily Companion", "description": "Daily companionship and light conversation.", "is_enabled": False},
    {"mode_key": "learning", "display_name": "Learning Companion", "description": "Learning and study companion.", "is_enabled": False},
    {"mode_key": "game", "display_name": "Game Companion", "description": "Gaming companion and strategy partner.", "is_enabled": False},
    {"mode_key": "character", "display_name": "Character Mode", "description": "Character-based roleplay companion.", "is_enabled": False},
    {"mode_key": "virtual_world", "display_name": "Virtual World Mode", "description": "Virtual world and scene companion.", "is_enabled": False},
]

DEFAULT_USER_EMAIL = "local@echora.dev"
DEFAULT_COMPANION_NAME = "Echora"


def seed(engine=None):
    """Seed the database with default Core conversation data. Idempotent."""
    if engine is None:
        engine = create_engine(settings.DATABASE_URL, echo=False)

    with Session(engine) as session:
        # ── 1. Default User ──────────────────────────────────────────
        user = session.query(User).filter(User.email == DEFAULT_USER_EMAIL).first()
        if user is None:
            user = User(
                display_name="Local User",
                email=DEFAULT_USER_EMAIL,
                timezone="America/Los_Angeles",
                locale="zh-CN",
            )
            session.add(user)
            session.flush()
            print(f"[seed] Created user: {user.display_name} ({user.id})")
        else:
            print(f"[seed] User already exists: {user.display_name} ({user.id})")

        # ── 2. Default Companion ─────────────────────────────────────
        companion = (
            session.query(Companion)
            .filter(Companion.user_id == user.id, Companion.name == DEFAULT_COMPANION_NAME)
            .first()
        )
        if companion is None:
            companion = Companion(
                user_id=user.id,
                name=DEFAULT_COMPANION_NAME,
                subtitle="A Persistent Companion Agent with Cognitive Memory",
                base_personality="warm, precise, structured, boundary-aware",
                current_mode="project",
                current_status="idle",
            )
            session.add(companion)
            session.flush()
            print(f"[seed] Created companion: {companion.name} ({companion.id})")
        else:
            print(f"[seed] Companion already exists: {companion.name} ({companion.id})")

        # ── 3. Default Companion Modes ───────────────────────────────
        for mode_def in MODES_TO_SEED:
            existing = (
                session.query(CompanionMode)
                .filter(
                    CompanionMode.companion_id == companion.id,
                    CompanionMode.mode_key == mode_def["mode_key"],
                )
                .first()
            )
            if existing is None:
                cm = CompanionMode(
                    companion_id=companion.id,
                    mode_key=mode_def["mode_key"],
                    display_name=mode_def["display_name"],
                    description=mode_def["description"],
                    is_enabled=mode_def["is_enabled"],
                )
                session.add(cm)
                print(f"[seed] Created mode: {mode_def['mode_key']} (enabled={mode_def['is_enabled']})")
            else:
                print(f"[seed] Mode already exists: {mode_def['mode_key']}")

        # ── 4. Default Boundary Settings ─────────────────────────────
        bs = (
            session.query(BoundarySetting)
            .filter(
                BoundarySetting.user_id == user.id,
                BoundarySetting.companion_id == companion.id,
            )
            .first()
        )
        if bs is None:
            bs = BoundarySetting(
                user_id=user.id,
                companion_id=companion.id,
                memory_save_policy="review_important",
                sensitive_memory_policy="always_review",
                proactive_level="medium",
                notification_surface="hub_queue_only",
                allow_auto_memory_low_risk=True,
                allow_proactive_presence=True,
                allow_sensitive_memory_without_review=False,
            )
            session.add(bs)
            session.flush()
            print(f"[seed] Created boundary settings ({bs.id})")
        else:
            print(f"[seed] Boundary settings already exist ({bs.id})")

        session.commit()
        print("[seed] Seed completed successfully.")


if __name__ == "__main__":
    seed()
