"""Rollback-safe PostgreSQL contract for learned-policy readiness readiness evidence."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    EvaluationMetric,
    EvaluationRun,
    RerankerTrainingExample,
)
from app.services import learned_policy_readiness_service as readiness
from app.services.persistence_helpers import get_engine, get_session


def test_readiness_run_persists_scoped_gate_and_rolls_back(monkeypatch) -> None:
    with get_session() as lookup:
        target = lookup.execute(
            select(RerankerTrainingExample.companion_id, func.count())
            .where(RerankerTrainingExample.deleted_at.is_(None))
            .group_by(RerankerTrainingExample.companion_id)
            .order_by(func.count().desc())
            .limit(1)
        ).first()
    assert target is not None, "learned-policy readiness contract requires one real training scope"
    companion_id = target[0]

    connection = get_engine().connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    @contextmanager
    def scoped_session():
        yield session

    monkeypatch.setattr(readiness, "get_session", scoped_session)
    run_id = None
    try:
        result = readiness.run_readiness_evaluation(companion_id)
        run_id = result["run"]["id"]
        assert result["activation_gate"]["active_allowed"] is False
        assert result["activation_gate"]["policy_modes"] == {
            "memory_reranker": "shadow",
            "contextual_presence_bandit": "shadow",
        }
        assert result["activation_gate"]["status"] in {
            "insufficient_data",
            "failed",
            "ready_for_separate_policy_review",
        }
        assert result["run"]["companion_id"] == str(companion_id)
        assert (
            session.scalar(
                select(func.count())
                .select_from(EvaluationMetric)
                .where(EvaluationMetric.evaluation_run_id == run_id)
            )
            == 9
        )
        latest = readiness.latest_readiness(companion_id)
        assert latest["evaluation_run_id"] == run_id
        assert latest["active_allowed"] is False
    finally:
        session.close()
        outer.rollback()
        connection.close()

    with get_session() as verification:
        assert verification.get(EvaluationRun, run_id) is None
